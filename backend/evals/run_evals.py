# ruff: noqa: T201
"""Run each case in evals/cases/ through the extractor and compare with expected.json.

    uv run python -m evals.run_evals [--case NAME] [--provider fake|openai]

Each case is a directory with `transcript.txt` and `expected.json`. Only the
fields listed in expected.json are compared (see `_view`). Raw outputs are
written to evals/out/<case>.json for diffing between prompt versions.
Run locally with your own OPENAI_API_KEY; this is not part of CI.
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.extraction.extractor import get_extractor
from app.extraction.run import census_from_seed, resolve_cards

CASES_DIR = Path(__file__).parent / "cases"
OUT_DIR = Path(__file__).parent / "out"


def _view(resolved_card: dict[str, Any]) -> dict[str, Any]:
    """The comparable subset of one resolved card, same shape as expected.json."""
    card = resolved_card["card"]
    matched = resolved_card["match"]["patient"]
    return {
        "bed": card["mention"]["bed"],
        "name": card["mention"]["name"],
        "match_status": resolved_card["match"]["status"],
        "matched_mrn": matched["mrn"] if matched else None,
        "illness_severity": card["illness_severity"],
        "contingencies": len(card["contingencies"]),
        "pending_results": len(card["pending_results"]),
        "action_items": [
            {
                "due_kind": item["due"]["kind"],
                "clock_time": item["due"]["clock_time"],
                "meridiem_stated": item["due"]["meridiem_stated"],
                "relative_minutes": item["due"]["relative_minutes"],
                "priority": item["priority"],
                "due_at": resolved["due_at"],
            }
            for item, resolved in zip(
                card["action_items"], resolved_card["action_items"], strict=True
            )
        ],
    }


def _name_words(value: str) -> list[str]:
    return re.sub(r"[^a-z ]", "", value.casefold()).split()


def _same(key: str, expected: Any, actual: Any) -> bool:
    if key == "name" and expected and actual:
        return _name_words(expected) == _name_words(actual)
    if key == "due_at" and expected and actual:
        return datetime.fromisoformat(expected) == datetime.fromisoformat(actual)
    return bool(expected == actual)


def _diff(expected: Any, actual: Any, path: str, key: str = "") -> list[str]:
    if isinstance(expected, dict) and isinstance(actual, dict):
        out: list[str] = []
        for k, v in expected.items():
            if k not in actual:
                out.append(f"{path}.{k}: missing in output")
            else:
                out.extend(_diff(v, actual[k], f"{path}.{k}", k))
        return out
    if isinstance(expected, list) and isinstance(actual, list):
        out = []
        if len(expected) != len(actual):
            out.append(f"{path}: expected {len(expected)} items, got {len(actual)}")
        for i, (e, a) in enumerate(zip(expected, actual, strict=False)):
            out.extend(_diff(e, a, f"{path}[{i}]"))
        return out
    if _same(key, expected, actual):
        return []
    return [f"{path}: expected {expected!r}, got {actual!r}"]


def run_case(case_dir: Path, provider: str | None) -> list[str]:
    expected = json.loads((case_dir / "expected.json").read_text())
    transcript = (case_dir / "transcript.txt").read_text()
    recorded_at = datetime.fromisoformat(expected["recorded_at"])

    active = settings
    if provider:
        active = settings.model_copy(update={"LLM_PROVIDER": provider})
    extraction = get_extractor(active).extract(transcript)
    resolved = resolve_cards(
        extraction, recorded_at, census_from_seed(), settings.hospital_tz
    )

    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / f"{case_dir.name}.json").write_text(
        json.dumps(
            {
                "provider": active.LLM_PROVIDER,
                "model": active.LLM_MODEL,
                "prompt_version": active.EXTRACTION_PROMPT_VERSION,
                "resolved": resolved,
            },
            indent=2,
        )
    )
    actual = {"patients": [_view(card) for card in resolved]}
    return _diff({"patients": expected["patients"]}, actual, "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--case", help="run only this case directory name")
    parser.add_argument("--provider", choices=["fake", "openai"], default=None)
    args = parser.parse_args(argv)

    case_dirs = sorted(
        d for d in CASES_DIR.iterdir() if d.is_dir() and (d / "expected.json").exists()
    )
    if args.case:
        case_dirs = [d for d in case_dirs if d.name == args.case]
        if not case_dirs:
            print(f"no case named {args.case!r}")
            return 2

    total = 0
    for case_dir in case_dirs:
        mismatches = run_case(case_dir, args.provider)
        total += len(mismatches)
        print(f"{case_dir.name}: {len(mismatches)} mismatch(es)")
        for line in mismatches:
            print(f"  {line}")
    print(f"\n{len(case_dirs)} case(s), {total} mismatch(es) total")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
