"""Score extraction runs against answer keys. Pure functions, no I/O.

A key (`expected.json`) lists, per patient: bed, name, match_status,
matched_mrn, illness_severity, the number of contingencies and pending
results, and action_items with the spoken due components, priority and the
resolved due_at. The private keys add `description` and `day` on each action
and a `must_not` list.

`score_run` compares one run with its key and returns counts; `aggregate`
adds runs up. Counts rather than rates, so repeated runs can be summed.
"""

import difflib
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Owner's value (12 Oct): two descriptions name the same action at or above it.
DESCRIPTION_MIN_RATIO = 0.6
# The prompt lets the model drop these when it copies the transcript.
FILLERS = frozenset({"um", "umm", "uh", "er", "erm", "ah", "eh", "yeah"})
_TITLES = frozenset({"mr", "mrs", "ms", "miss", "dr", "sahab", "sahib", "ji"})
DUE_FIELDS = (
    "due_kind",
    "clock_time",
    "meridiem_stated",
    "relative_minutes",
    "day",
    "due_at",
)
COUNTS = (
    "patients_expected",
    "patients_found",
    "patients_extra",
    "match_correct",
    "severity_correct",
    "contingencies_correct",
    "pending_correct",
    "actions_expected",
    "actions_found",
    "actions_extra",
    "due_correct",
    "priority_correct",
    "hallucinations",
    "duplicates",
    "must_not_violations",
    "errors",
)
# rate name -> (numerator count, denominator count)
RATES = {
    "patient_recall": ("patients_found", "patients_expected"),
    "match_accuracy": ("match_correct", "patients_found"),
    "severity_accuracy": ("severity_correct", "patients_found"),
    "contingency_accuracy": ("contingencies_correct", "patients_found"),
    "pending_accuracy": ("pending_correct", "patients_found"),
    "action_recall": ("actions_found", "actions_expected"),
    "due_accuracy": ("due_correct", "actions_found"),
    "priority_accuracy": ("priority_correct", "actions_found"),
}


@dataclass
class RunScore:
    counts: Counter[str] = field(default_factory=Counter)
    diffs: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        c = self.counts
        found, actions = c["patients_found"], c["actions_found"]
        return (
            found == c["patients_expected"]
            and actions == c["actions_expected"]
            and c["match_correct"] == found
            and c["severity_correct"] == found
            and c["contingencies_correct"] == found
            and c["pending_correct"] == found
            and c["due_correct"] == actions
            and c["priority_correct"] == actions
            and not any(
                c[k]
                for k in (
                    "patients_extra",
                    "actions_extra",
                    "hallucinations",
                    "duplicates",
                    "must_not_violations",
                    "errors",
                )
            )
        )


def view_card(resolved: dict[str, Any]) -> dict[str, Any]:
    """One resolved card (from `resolve_cards`) in the shape of a key's patient."""
    card = resolved["card"]
    matched = resolved["match"]["patient"]
    quoted = [card["mention"]["verbatim"]] + [
        entry["verbatim"]
        for section in ("action_items", "contingencies", "pending_results")
        for entry in card[section]
    ]
    return {
        "bed": card["mention"]["bed"],
        "name": card["mention"]["name"],
        "mention_verbatim": card["mention"]["verbatim"],
        "match_status": resolved["match"]["status"],
        "matched_mrn": matched["mrn"] if matched else None,
        "illness_severity": card["illness_severity"],
        "contingencies": len(card["contingencies"]),
        "pending_results": len(card["pending_results"]),
        "action_items": [
            {
                "description": item["description"],
                "due_kind": item["due"]["kind"],
                "clock_time": item["due"]["clock_time"],
                "meridiem_stated": item["due"]["meridiem_stated"],
                "relative_minutes": item["due"]["relative_minutes"],
                "day": item["due"].get("day"),
                "priority": item["priority"],
                "due_at": done["due_at"],
            }
            for item, done in zip(
                card["action_items"], resolved["action_items"], strict=True
            )
        ],
        "verbatims": [text for text in quoted if text],
    }


def score_run(
    key: dict[str, Any],
    actual: list[dict[str, Any]],
    transcript: str,
    error: str | None = None,
) -> RunScore:
    """Compare one run's cards (`view_card` shape) with the answer key."""
    expected: list[dict[str, Any]] = key["patients"]
    score = RunScore()
    c, diffs = score.counts, score.diffs
    c["patients_expected"] = len(expected)
    c["actions_expected"] = sum(len(e["action_items"]) for e in expected)
    if error is not None:
        c["errors"] = 1
        diffs.append(f"model call failed: {error}")

    pairs = pair_cards(expected, actual)
    for i, j in pairs:
        _score_card(expected[i], actual[j], score)
    paired_expected = {i for i, _ in pairs}
    paired_actual = {j for _, j in pairs}
    for i, e in enumerate(expected):
        if i not in paired_expected:
            diffs.append(f"{_label(e)}: patient missing")
    for j, a in enumerate(actual):
        if j not in paired_actual:
            c["patients_extra"] += 1
            c["actions_extra"] += len(a["action_items"])
            diffs.append(f"{_label(a)}: extra card")

    by_mrn = Counter(a["matched_mrn"] for a in actual if a["matched_mrn"])
    for mrn, n in by_mrn.items():
        if n > 1:
            c["duplicates"] += n - 1
            diffs.append(f"{mrn}: {n} cards for one patient")

    spoken = f" {normalise(transcript)} "
    for a in actual:
        for text in a["verbatims"]:
            words = normalise(text)
            if words and f" {words} " not in spoken:
                c["hallucinations"] += 1
                diffs.append(f"{_label(a)}: text not in transcript: {text!r}")

    extra = [a for j, a in enumerate(actual) if j not in paired_actual]
    for rule in key.get("must_not", []):
        hits = must_not_hits(rule, actual, extra)
        if hits:
            c["must_not_violations"] += hits
            shown = {k: v for k, v in rule.items() if k != "why"}
            diffs.append(f"must not {shown} ({rule.get('why', '')}): {hits}")
    return score


def pair_cards(
    expected: list[dict[str, Any]], actual: list[dict[str, Any]]
) -> list[tuple[int, int]]:
    """One-to-one: same matched MRN, else same bed, else same name words."""
    pairs: list[tuple[int, int]] = []
    used_e: set[int] = set()
    used_a: set[int] = set()
    for cue in (
        lambda card: card["matched_mrn"],
        lambda card: _bed(card["bed"]),
        lambda card: " ".join(_name_words(card["name"])),
    ):
        for i, e in enumerate(expected):
            if i in used_e or not cue(e):
                continue
            for j, a in enumerate(actual):
                if j not in used_a and cue(a) == cue(e):
                    pairs.append((i, j))
                    used_e.add(i)
                    used_a.add(j)
                    break
    return sorted(pairs)


def pair_actions(
    expected: list[dict[str, Any]], actual: list[dict[str, Any]]
) -> list[tuple[int, int]]:
    """Same due_at (both empty counts) and, when the key has one, a close
    enough description; the closest description wins."""
    pairs: list[tuple[int, int]] = []
    used: set[int] = set()
    for i, e in enumerate(expected):
        best, best_ratio = None, -1.0
        for j, a in enumerate(actual):
            if j in used or not _same("due_at", e.get("due_at"), a.get("due_at")):
                continue
            ratio = 1.0
            if e.get("description"):
                ratio = description_ratio(e["description"], a["description"])
                if ratio < DESCRIPTION_MIN_RATIO:
                    continue
            if ratio > best_ratio:
                best, best_ratio = j, ratio
        if best is not None:
            used.add(best)
            pairs.append((i, best))
    return pairs


def must_not_hits(
    rule: dict[str, Any],
    actual: list[dict[str, Any]],
    extra: list[dict[str, Any]],
) -> int:
    """How many times one `must_not` entry is broken. Shapes: {action[, bed]},
    {bed, duplicate}, {verbatim}, {bed[, name]}."""
    if "action" in rule:
        banned = set(_words(rule["action"]))
        cards = [
            a
            for a in actual
            if "bed" not in rule or _bed(a["bed"]) == _bed(rule["bed"])
        ]
        # Every word must appear, so "hold enoxaparin" never breaks
        # "give enoxaparin"; a reworded breach is missed.
        return sum(
            1
            for a in cards
            for item in a["action_items"]
            if banned <= set(_words(item["description"]))
        )
    if rule.get("duplicate"):
        same_bed = [a for a in actual if _bed(a["bed"]) == _bed(rule["bed"])]
        return max(0, len(same_bed) - 1)
    if "verbatim" in rule:
        phrase = normalise(rule["verbatim"])
        return sum(
            1
            for a in extra
            if (said := normalise(a["mention_verbatim"] or ""))
            and (said in phrase or phrase in said)
        )
    if "bed" in rule:
        name = set(_name_words(rule.get("name")))
        return sum(
            1
            for a in actual
            if _bed(a["bed"]) == _bed(rule["bed"])
            and (not name or name & set(_name_words(a["name"])))
        )
    raise ValueError(f"unknown must_not shape: {rule}")


def aggregate(runs_by_case: dict[str, list[RunScore]]) -> dict[str, Any]:
    """Sum runs; pass rate, cases consistent across repeats, and the spread of
    the pass rate between repeat 1, 2, 3..."""
    counts: Counter[str] = Counter()
    for runs in runs_by_case.values():
        for run in runs:
            counts.update(run.counts)
    all_runs = [run for runs in runs_by_case.values() for run in runs]
    passed = sum(run.passed for run in all_runs)
    consistent = sum(
        len({run.passed for run in runs}) == 1 for runs in runs_by_case.values() if runs
    )
    repeats = max((len(runs) for runs in runs_by_case.values()), default=0)
    per_repeat = []
    for r in range(repeats):
        nth = [runs[r].passed for runs in runs_by_case.values() if len(runs) > r]
        per_repeat.append(sum(nth) / len(nth))
    return {
        "runs": len(all_runs),
        "passed": passed,
        "pass_rate": passed / len(all_runs) if all_runs else None,
        "cases": len(runs_by_case),
        "consistent_cases": consistent,
        "pass_rate_spread": [min(per_repeat), max(per_repeat)] if per_repeat else None,
        "counts": {k: counts[k] for k in COUNTS},
        "rates": rates(counts),
    }


def rates(counts: Counter[str]) -> dict[str, float | None]:
    out = {
        name: counts[num] / counts[den] if counts[den] else None
        for name, (num, den) in RATES.items()
    }
    produced = counts["actions_found"] + counts["actions_extra"]
    out["action_precision"] = counts["actions_found"] / produced if produced else None
    return out


def normalise(text: str) -> str:
    """Lower case, punctuation to spaces, fillers dropped."""
    return " ".join(w for w in _words(text) if w not in FILLERS)


def description_ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalise(a), normalise(b)).ratio()


def _score_card(e: dict[str, Any], a: dict[str, Any], score: RunScore) -> None:
    c, diffs, label = score.counts, score.diffs, _label(e)
    c["patients_found"] += 1
    if (e["match_status"], e["matched_mrn"]) == (a["match_status"], a["matched_mrn"]):
        c["match_correct"] += 1
    else:
        diffs.append(
            f"{label}: match {a['match_status']} {a['matched_mrn']}, "
            f"expected {e['match_status']} {e['matched_mrn']}"
        )
    for key_field, counter in (
        ("illness_severity", "severity_correct"),
        ("contingencies", "contingencies_correct"),
        ("pending_results", "pending_correct"),
    ):
        if e[key_field] == a[key_field]:
            c[counter] += 1
        else:
            diffs.append(
                f"{label}: {key_field} {a[key_field]!r}, expected {e[key_field]!r}"
            )

    expected, actual = e["action_items"], a["action_items"]
    pairs = pair_actions(expected, actual)
    c["actions_found"] += len(pairs)
    c["actions_extra"] += len(actual) - len(pairs)
    for i, j in pairs:
        want, got = expected[i], actual[j]
        what = _action_label(want)
        wrong = [f for f in DUE_FIELDS if not _same(f, want.get(f), got.get(f))]
        if wrong:
            detail = ", ".join(
                f"{f} {got.get(f)!r} expected {want.get(f)!r}" for f in wrong
            )
            diffs.append(f"{label}: {what}: {detail}")
        else:
            c["due_correct"] += 1
        if want["priority"] == got["priority"]:
            c["priority_correct"] += 1
        else:
            diffs.append(
                f"{label}: {what}: priority {got['priority']!r}, expected {want['priority']!r}"
            )
    for i, want in enumerate(expected):
        if i not in {p[0] for p in pairs}:
            diffs.append(f"{label}: action missing: {_action_label(want)}")
    for j, got in enumerate(actual):
        if j not in {p[1] for p in pairs}:
            diffs.append(f"{label}: extra action: {_action_label(got)}")


def _same(key: str, expected: Any, actual: Any) -> bool:
    if key == "due_at" and expected and actual:
        return datetime.fromisoformat(expected) == datetime.fromisoformat(actual)
    return bool(expected == actual)


def _label(card: dict[str, Any]) -> str:
    bed = f"bed {card['bed']}" if card.get("bed") else "no bed"
    return f"{bed} {card.get('name') or ''}".strip()


def _action_label(item: dict[str, Any]) -> str:
    return item.get("description") or f"action due {item.get('due_at')}"


def _words(text: str | None) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").casefold())


def _name_words(name: str | None) -> list[str]:
    return [w for w in _words(name) if w not in _TITLES]


def _bed(bed: str | None) -> str:
    digits = re.sub(r"\D", "", bed or "")
    return digits or (bed or "").strip().casefold()
