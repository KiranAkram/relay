"""Dev CLI: transcript or audio file -> extraction -> resolved due times + census match.

    uv run python -m app.extraction.run SOURCE [--recorded-at ISO]
        [--provider fake|openai] [--stt-provider fake|openai]

SOURCE is a .txt transcript or an audio file (mp3, m4a, wav, webm, ...), which
is transcribed first. No DB: the census is the seed list. Writes one JSON
document to stdout. `resolve_cards` is also used by `evals/run_evals.py`.
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
from app.extraction.resolve import resolve_action_item
from app.extraction.schema import HandoverExtraction
from app.models import Patient
from app.seed.patients import SEED_PATIENTS
from app.services.stt import AUDIO_SUFFIXES, get_transcriber


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
                    resolve_action_item(item, recorded_at, tz)
                    for item in card.action_items
                ],
            }
        )
    return cards


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("source", type=Path, help=".txt transcript or audio file")
    parser.add_argument(
        "--recorded-at",
        type=datetime.fromisoformat,
        default=None,
        help="ISO timestamp of the recording (default: now, UTC)",
    )
    parser.add_argument("--provider", choices=["fake", "openai"], default=None)
    parser.add_argument("--stt-provider", choices=["fake", "openai"], default=None)
    args = parser.parse_args(argv)

    recorded_at: datetime = args.recorded_at or datetime.now(UTC)
    if recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=settings.hospital_tz)

    overrides: dict[str, str] = {}
    if args.provider:
        overrides["LLM_PROVIDER"] = args.provider
    if args.stt_provider:
        overrides["STT_PROVIDER"] = args.stt_provider
    active_settings = settings.model_copy(update=overrides) if overrides else settings

    census = census_from_seed()
    source: Path = args.source
    output: dict[str, Any] = {
        "provider": active_settings.LLM_PROVIDER,
        "model": active_settings.LLM_MODEL,
        "prompt_version": active_settings.EXTRACTION_PROMPT_VERSION,
        "recorded_at": recorded_at.isoformat(),
    }
    if source.suffix.lower() in AUDIO_SUFFIXES:
        hints = sorted({p.family_name for p in census})
        transcript = get_transcriber(active_settings).transcribe(
            source.read_bytes(), source.name, hints
        )
        output["stt_provider"] = active_settings.STT_PROVIDER
        output["stt_model"] = active_settings.STT_MODEL
    else:
        transcript = source.read_text()
    output["transcript"] = transcript

    extraction = get_extractor(active_settings).extract(transcript)
    output["patients"] = resolve_cards(
        extraction, recorded_at, census, settings.hospital_tz
    )
    sys.stdout.write(json.dumps(output, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
