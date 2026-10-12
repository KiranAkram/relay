# ruff: noqa: T201
"""Score the extractor against answer keys, across models, prompt versions and repeats.

    uv run python -m evals.run_evals [--cases DIR ...] [--case NAME]
        [--repeat N] [--model M ...] [--prompt-version V ...]
        [--provider fake|openai]

A case is either a directory `<name>/` holding `transcript.txt` and
`expected.json` (evals/cases, the default) or a flat `<name>.expected.json`
whose transcript is the key's `transcript_file`, else `<name>.transcript.txt`,
else `<name>.txt` (the private scripts). Every model x prompt version is one
configuration; each case runs `--repeat` times per configuration. Each
invocation writes to its own folder evals/out/<UTC time>/: raw outputs in
<model>_<prompt>/<case>.<run>.json, and summary.md, summary.json and
report.html (open it in a browser). The header records the git commit,
reasoning effort and a fingerprint of each prompt. A report, not a gate: the
exit code is 0 whatever the scores.
Run locally with your own OPENAI_API_KEY; this is not part of CI.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.extraction.extractor import REASONING_EFFORT, get_extractor
from app.extraction.prompt import PROMPTS
from app.extraction.run import census_from_seed, resolve_cards
from evals.metrics import RunScore, aggregate, score_run, view_card
from evals.report import render_html, render_markdown

CASES_DIR = Path(__file__).parent / "cases"
OUT_DIR = Path(__file__).parent / "out"


@dataclass
class Case:
    name: str
    transcript: str
    key: dict[str, Any]


def load_cases(dirs: list[Path]) -> list[Case]:
    cases: dict[str, Case] = {}
    for root in dirs:
        found: list[Case] = []
        for sub in sorted(p for p in root.iterdir() if p.is_dir()):
            if (sub / "expected.json").exists():
                key = json.loads((sub / "expected.json").read_text())
                found.append(Case(sub.name, (sub / "transcript.txt").read_text(), key))
        for key_file in sorted(root.glob("*.expected.json")):
            name = key_file.name.removesuffix(".expected.json")
            key = json.loads(key_file.read_text())
            found.append(Case(name, _flat_transcript(root, name, key), key))
        for case in found:
            if case.name in cases:
                raise ValueError(f"case {case.name!r} found twice")
            cases[case.name] = case
    return list(cases.values())


def _flat_transcript(root: Path, name: str, key: dict[str, Any]) -> str:
    candidates = [key.get("transcript_file"), f"{name}.transcript.txt", f"{name}.txt"]
    for candidate in candidates:
        if candidate and (root / candidate).exists():
            return (root / candidate).read_text()
    raise FileNotFoundError(f"no transcript for case {name!r} in {root}")


def run_configuration(
    model: str,
    prompt_version: str,
    provider: str,
    cases: list[Case],
    repeat: int,
    out_root: Path,
) -> dict[str, list[RunScore]]:
    active = settings.model_copy(
        update={
            "LLM_PROVIDER": provider,
            "LLM_MODEL": model,
            "EXTRACTION_PROMPT_VERSION": prompt_version,
        }
    )
    extractor = get_extractor(active)
    census = census_from_seed()
    out_dir = out_root / f"{model}_{prompt_version}"
    out_dir.mkdir(parents=True, exist_ok=True)

    scores: dict[str, list[RunScore]] = {}
    for case in cases:
        recorded_at = datetime.fromisoformat(case.key["recorded_at"])
        scores[case.name] = []
        for run in range(1, repeat + 1):
            resolved: list[dict[str, Any]] = []
            error = None
            try:
                extraction = extractor.extract(case.transcript)
            except Exception as exc:  # one failed model call must not end the run
                error = f"{type(exc).__name__}: {exc}"
            else:
                # Our own timing and matching code: a bug here must stop the run.
                resolved = resolve_cards(
                    extraction, recorded_at, census, settings.hospital_tz
                )
            (out_dir / f"{case.name}.{run}.json").write_text(
                json.dumps(
                    {
                        "provider": provider,
                        "model": model,
                        "prompt_version": prompt_version,
                        "recorded_at": case.key["recorded_at"],
                        "error": error,
                        "resolved": resolved,
                    },
                    indent=2,
                )
            )
            score = score_run(
                case.key, [view_card(r) for r in resolved], case.transcript, error
            )
            scores[case.name].append(score)
            verdict = "pass" if score.passed else f"FAIL ({len(score.diffs)})"
            print(f"{model}_{prompt_version}  {case.name}  run {run}: {verdict}")
            if not score.passed:
                for line in score.diffs:
                    print(f"    {line}")
    return scores


def git_commit() -> str:
    """Short commit of the code under test, marked when the tree has changes."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{commit} + uncommitted changes" if dirty else commit


def prompt_fingerprint(version: str) -> str:
    return hashlib.sha256(PROMPTS[version].encode()).hexdigest()[:12]


def build_summary(
    provider: str,
    repeat: int,
    cases: list[Case],
    results: dict[tuple[str, str], dict[str, list[RunScore]]],
    commit: str,
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "provider": provider,
        "git_commit": commit,
        "reasoning_effort": REASONING_EFFORT,
        "repeat": repeat,
        "cases": [case.name for case in cases],
        "configurations": [
            {
                "name": f"{model} + {prompt_version}",
                "model": model,
                "prompt_version": prompt_version,
                "prompt_fingerprint": prompt_fingerprint(prompt_version),
                "aggregate": aggregate(scores),
                "cases": {
                    name: {
                        "aggregate": aggregate({name: runs}),
                        "runs": [
                            {
                                "run": i,
                                "passed": run.passed,
                                "counts": dict(run.counts),
                                "diffs": run.diffs,
                            }
                            for i, run in enumerate(runs, start=1)
                        ],
                    }
                    for name, runs in scores.items()
                },
            }
            for (model, prompt_version), scores in results.items()
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--cases",
        type=Path,
        action="append",
        help="case directory, repeatable (default: evals/cases)",
    )
    parser.add_argument("--case", help="run only this case")
    parser.add_argument("--repeat", type=int, default=1, help="runs per case")
    parser.add_argument("--model", action="append", help="repeatable")
    parser.add_argument("--prompt-version", action="append", help="repeatable")
    parser.add_argument("--provider", choices=["fake", "openai"], default=None)
    args = parser.parse_args(argv)

    cases = load_cases(args.cases or [CASES_DIR])
    if args.case:
        cases = [c for c in cases if c.name == args.case]
        if not cases:
            print(f"no case named {args.case!r}")
            return 2
    if args.repeat < 1:
        print("--repeat must be at least 1")
        return 2
    models: list[str] = args.model or [settings.LLM_MODEL]
    prompts: list[str] = args.prompt_version or [settings.EXTRACTION_PROMPT_VERSION]
    unknown = [p for p in prompts if p not in PROMPTS]
    if unknown:
        print(f"unknown prompt version(s): {', '.join(unknown)}")
        return 2
    provider: str = args.provider or settings.LLM_PROVIDER

    calls = len(models) * len(prompts) * len(cases) * args.repeat
    if provider == "openai":
        print(
            f"{calls} model calls: {len(models)} model(s) x {len(prompts)} prompt "
            f"version(s) x {len(cases)} case(s) x {args.repeat} repeat(s)\n"
        )

    commit = git_commit()
    out_root = OUT_DIR / datetime.now(UTC).strftime("%Y%m%d-%H%M%SZ")
    out_root.mkdir(parents=True)
    results = {
        (model, prompt): run_configuration(
            model, prompt, provider, cases, args.repeat, out_root
        )
        for model in models
        for prompt in prompts
    }
    summary = build_summary(provider, args.repeat, cases, results, commit)
    markdown = render_markdown(summary)
    print("\n" + markdown)

    (out_root / "summary.md").write_text(markdown)
    (out_root / "summary.json").write_text(json.dumps(summary, indent=2))
    report = out_root / "report.html"
    report.write_text(render_html(summary, {c.name: c.transcript for c in cases}))
    print(f"Report: {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
