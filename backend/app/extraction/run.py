"""Dev CLI: transcript file -> extraction -> resolved due times + census match.

    uv run python -m app.extraction.run transcript.txt [--recorded-at ISO] [--provider fake|openai]

No DB: the census is the seed list. Writes one JSON document to stdout.
`resolve_cards` is also used by `evals/run_evals.py`; it moves into
pipeline.py in step 4.
"""

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.extraction.extractor import get_extractor
from app.extraction.matching import match_mention
from app.extraction.schema import HandoverExtraction
from app.extraction.timing import resolve_due
from app.models import Patient
from app.seed.patients import SEED_PATIENTS


def census_from_seed() -> list[Patient]:
    return [Patient.model_validate(p) for p in SEED_PATIENTS]


def _patient_ref(patient: Patient) -> dict[str, str | None]:
    return {
        "mrn": patient.mrn,
        "name": f"{patient.given_name} {patient.family_name}",
        "bed": patient.bed,
    }


def resolve_cards(
    extraction: HandoverExtraction,
    recorded_at: datetime,
    census: list[Patient],
    tz: ZoneInfo,
) -> list[dict[str, Any]]:
    by_id: dict[uuid.UUID, Patient] = {p.id: p for p in census}
    cards: list[dict[str, Any]] = []
    for card in extraction.patients:
        match = match_mention(card.mention, census)
        cards.append(
            {
                "card": card.model_dump(mode="json"),
                "match": {
                    "status": match.status.value,
                    "patient": _patient_ref(by_id[match.patient_id])
                    if match.patient_id
                    else None,
                    "candidates": [
                        {
                            **_patient_ref(by_id[c.patient_id]),
                            "reason": c.reason,
                            "score": round(c.score, 3),
                        }
                        for c in match.candidates
                    ],
                },
                "action_items": [
                    {
                        "description": item.description,
                        "priority": item.priority.value,
                        "due_phrase": item.due.phrase,
                        **resolve_due(item.due, recorded_at, tz).model_dump(
                            mode="json"
                        ),
                    }
                    for item in card.action_items
                ],
            }
        )
    return cards


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("transcript", type=Path)
    parser.add_argument(
        "--recorded-at",
        type=datetime.fromisoformat,
        default=None,
        help="ISO timestamp of the recording (default: now, UTC)",
    )
    parser.add_argument("--provider", choices=["fake", "openai"], default=None)
    args = parser.parse_args(argv)

    recorded_at: datetime = args.recorded_at or datetime.now(UTC)
    if recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=settings.hospital_tz)

    active_settings = settings
    if args.provider:
        active_settings = settings.model_copy(update={"LLM_PROVIDER": args.provider})
    extractor = get_extractor(active_settings)
    extraction = extractor.extract(args.transcript.read_text())

    output = {
        "provider": active_settings.LLM_PROVIDER,
        "model": active_settings.LLM_MODEL,
        "prompt_version": active_settings.EXTRACTION_PROMPT_VERSION,
        "recorded_at": recorded_at.isoformat(),
        "patients": resolve_cards(
            extraction, recorded_at, census_from_seed(), settings.hospital_tz
        ),
    }
    sys.stdout.write(json.dumps(output, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
