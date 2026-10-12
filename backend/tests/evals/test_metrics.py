import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from app.core.config import settings
from app.extraction.extractor import DEMO_EXTRACTION
from app.extraction.run import census_from_seed, resolve_cards
from evals.metrics import (
    aggregate,
    must_not_hits,
    pair_actions,
    score_run,
    view_card,
)
from evals.report import render_html, render_markdown
from evals.run_evals import CASES_DIR, build_summary, load_cases

TRANSCRIPT = (
    "Bed seven, Mr Baig, um, he's a watcher. Give metoprolol at half eight. "
    "That's everyone."
)


def _action(**overrides: Any) -> dict[str, Any]:
    action = {
        "description": "give metoprolol",
        "due_kind": "clock",
        "clock_time": "08:30",
        "meridiem_stated": False,
        "relative_minutes": None,
        "day": None,
        "priority": "routine",
        "due_at": "2026-10-09T03:30:00Z",
    }
    return action | overrides


def _card(**overrides: Any) -> dict[str, Any]:
    card = {
        "bed": "7",
        "name": "Mr Baig",
        "mention_verbatim": "Bed seven, Mr Baig",
        "match_status": "matched",
        "matched_mrn": "MRN-100007",
        "illness_severity": "watcher",
        "contingencies": 0,
        "pending_results": 0,
        "action_items": [_action()],
        "verbatims": ["Bed seven, Mr Baig", "Give metoprolol at half eight"],
    }
    return card | overrides


def _key(
    *patients: dict[str, Any], must_not: list[Any] | None = None
) -> dict[str, Any]:
    return {
        "recorded_at": "2026-10-09T08:00:00+05:00",
        "patients": list(patients),
        "must_not": must_not or [],
    }


def test_identical_run_passes() -> None:
    score = score_run(_key(_card()), [_card()], TRANSCRIPT)
    assert score.passed
    assert score.counts["patients_found"] == 1
    assert score.counts["due_correct"] == 1
    assert score.diffs == []


def test_missing_patient_and_extra_card() -> None:
    other = _card(bed="9", name="Asad Iqbal", matched_mrn="MRN-100009", verbatims=[])
    score = score_run(_key(_card()), [other], TRANSCRIPT)
    assert score.counts["patients_found"] == 0
    assert score.counts["patients_extra"] == 1
    assert score.counts["actions_extra"] == 1
    assert not score.passed


def test_cards_pair_by_bed_then_name_when_no_mrn() -> None:
    by_bed = _card(name="Mr Khan", match_status="ambiguous", matched_mrn=None)
    score = score_run(_key(_card()), [by_bed], TRANSCRIPT)
    assert score.counts["patients_found"] == 1
    assert score.counts["match_correct"] == 0

    no_bed = _card(
        bed=None, name="Mr. Khan", match_status="ambiguous", matched_mrn=None
    )
    score = score_run(_key(no_bed | {"name": "Mr Khan"}), [no_bed], TRANSCRIPT)
    assert score.counts["patients_found"] == 1
    assert score.counts["match_correct"] == 1


def test_severity_contingency_and_pending_counts() -> None:
    actual = _card(illness_severity="unstable", contingencies=1, pending_results=1)
    score = score_run(_key(_card()), [actual], TRANSCRIPT)
    assert score.counts["severity_correct"] == 0
    assert score.counts["contingencies_correct"] == 0
    assert score.counts["pending_correct"] == 0
    assert any("illness_severity" in d for d in score.diffs)


def test_action_needs_same_due_and_close_description() -> None:
    expected = [_action()]
    assert pair_actions(expected, [_action(description="Give the metoprolol")]) == [
        (0, 0)
    ]
    assert pair_actions(expected, [_action(description="chase echo report")]) == []
    assert pair_actions(expected, [_action(due_at="2026-10-09T15:30:00Z")]) == []
    # Public keys have no description: due time alone pairs.
    no_description = {k: v for k, v in _action().items() if k != "description"}
    assert pair_actions([no_description], [_action(description="anything")]) == [(0, 0)]


def test_wrong_day_or_priority_is_counted_on_a_found_action() -> None:
    actual = _card(action_items=[_action(day="today", priority="urgent")])
    score = score_run(_key(_card()), [actual], TRANSCRIPT)
    assert score.counts["actions_found"] == 1
    assert score.counts["due_correct"] == 0
    assert score.counts["priority_correct"] == 0


def test_missing_day_in_a_key_counts_as_none() -> None:
    expected = _card(action_items=[{k: v for k, v in _action().items() if k != "day"}])
    score = score_run(_key(expected), [_card()], TRANSCRIPT)
    assert score.counts["due_correct"] == 1


def test_text_not_in_transcript_counts_but_dropped_fillers_do_not() -> None:
    actual = _card(verbatims=["he's a watcher", "Give metoprolol at nine"])
    score = score_run(_key(_card()), [actual], TRANSCRIPT)
    assert score.counts["hallucinations"] == 1
    clean = _card(verbatims=["Mr Baig he's a watcher"])
    assert score_run(_key(_card()), [clean], TRANSCRIPT).counts["hallucinations"] == 0


def test_two_cards_for_one_patient_is_a_duplicate() -> None:
    again = _card(bed=None, name=None, action_items=[])
    score = score_run(_key(_card()), [_card(), again], TRANSCRIPT)
    assert score.counts["duplicates"] == 1
    assert score.counts["patients_extra"] == 1


def test_must_not_action_needs_every_word() -> None:
    hold = _card(action_items=[_action(description="hold enoxaparin tonight")])
    give = _card(action_items=[_action(description="Give the enoxaparin")])
    rule = {"why": "negative instruction", "action": "give enoxaparin"}
    assert must_not_hits(rule, [hold], []) == 0
    assert must_not_hits(rule, [give], []) == 1


def test_must_not_action_limited_to_a_bed() -> None:
    echo = _card(bed="14", action_items=[_action(description="repeat echo")])
    rule = {"why": "retracted", "action": "repeat echo", "bed": "14"}
    assert must_not_hits(rule, [echo], []) == 1
    assert must_not_hits(rule | {"bed": "3"}, [echo], []) == 0


def test_must_not_duplicate_bed() -> None:
    rule = {"why": "same patient revisited", "bed": "3", "duplicate": True}
    cards = [_card(bed="3"), _card(bed="3"), _card(bed="10")]
    assert must_not_hits(rule, cards, []) == 1


def test_must_not_verbatim_only_on_extra_cards() -> None:
    rule = {
        "why": "closing remark",
        "verbatim": "Fourteen to twenty-two are all stable",
    }
    closing = _card(bed=None, mention_verbatim="Fourteen to twenty-two")
    assert must_not_hits(rule, [closing], [closing]) == 1
    assert must_not_hits(rule, [closing], []) == 0


def test_must_not_bed_with_and_without_name() -> None:
    akhtar = _card(bed="19", name="Robina Akhtar")
    mirza = _card(bed="19", name="Mr Mirza")
    moved = {"why": "old bed", "bed": "19", "name": "Robina Akhtar"}
    assert must_not_hits(moved, [akhtar, mirza], []) == 1
    assert must_not_hits({"why": "passing mention", "bed": "19"}, [mirza], []) == 1


def test_must_not_breach_fails_the_run() -> None:
    key = _key(_card(), must_not=[{"why": "old bed", "bed": "6"}])
    score = score_run(key, [_card(), _card(bed="6", matched_mrn=None)], TRANSCRIPT)
    assert score.counts["must_not_violations"] == 1
    assert not score.passed


def test_failed_model_call_counts_as_error() -> None:
    score = score_run(_key(_card()), [], TRANSCRIPT, error="APIError: timeout")
    assert score.counts["errors"] == 1
    assert score.counts["patients_found"] == 0
    assert not score.passed


def test_aggregate_sums_runs_and_reports_spread() -> None:
    good = score_run(_key(_card()), [_card()], TRANSCRIPT)
    bad = score_run(_key(_card()), [], TRANSCRIPT)
    agg = aggregate({"a": [good, good, bad], "b": [good, good, good]})
    assert agg["runs"] == 6
    assert agg["passed"] == 5
    assert agg["consistent_cases"] == 1
    assert agg["pass_rate_spread"] == [0.5, 1.0]
    assert agg["rates"]["patient_recall"] == pytest.approx(5 / 6)
    two_of_three = aggregate({"a": [good, good, bad]})
    assert two_of_three["pass_rate"] == pytest.approx(2 / 3)


def test_view_card_and_demo_case_pass_with_the_fake_extractor() -> None:
    case = next(c for c in load_cases([CASES_DIR]) if c.name == "demo_bed7")
    resolved = resolve_cards(
        DEMO_EXTRACTION,
        datetime.fromisoformat(case.key["recorded_at"]),
        census_from_seed(),
        settings.hospital_tz,
    )
    views = [view_card(r) for r in resolved]
    assert views[0]["action_items"][0]["day"] is None
    score = score_run(case.key, views, case.transcript)
    assert score.passed, score.diffs


def test_load_cases_reads_both_layouts(tmp_path: Path) -> None:
    folder = tmp_path / "public" / "one"
    folder.mkdir(parents=True)
    (folder / "expected.json").write_text(json.dumps(_key()))
    (folder / "transcript.txt").write_text("folder layout")

    flat = tmp_path / "private"
    flat.mkdir()
    (flat / "two.expected.json").write_text(json.dumps(_key()))
    (flat / "two.txt").write_text("as spoken")
    (flat / "two.transcript.txt").write_text("as transcribed")
    (flat / "three.expected.json").write_text(
        json.dumps(_key() | {"transcript_file": "other.txt"})
    )
    (flat / "three.txt").write_text("as spoken")
    (flat / "other.txt").write_text("named in the key")

    cases = {c.name: c.transcript for c in load_cases([tmp_path / "public", flat])}
    assert cases == {
        "one": "folder layout",
        "three": "named in the key",
        "two": "as transcribed",
    }
    with pytest.raises(ValueError):
        load_cases([flat, flat])


def test_report_renders_both_formats() -> None:
    score = score_run(_key(_card()), [], TRANSCRIPT)
    case = load_cases([CASES_DIR])[0]
    summary = build_summary(
        "fake", 1, [case], {("gpt-5-mini", "v3"): {case.name: [score]}}
    )
    markdown = render_markdown(summary)
    assert "gpt-5-mini + v3" in markdown
    assert f"| {case.name} | 0/1 |" in markdown
    page = render_html(summary, {case.name: "<script>x</script>"})
    assert "&lt;script&gt;" in page
    assert "<script>x" not in page
