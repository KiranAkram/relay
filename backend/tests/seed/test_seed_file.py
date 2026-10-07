"""Seed file shape. No database: safe under `--noconftest`."""

import pytest
from pydantic import ValidationError

from app.models import CodeStatus, ObservationInterpretation
from app.seed.patients import SEED, SEED_PATIENTS, SeedFile, load_seed


def test_seed_file_loads_22_synthetic_patients_one_per_bed() -> None:
    seed = load_seed()
    assert seed.unit == "CCU"
    assert len(seed.patients) == 22
    assert len({p.mrn for p in seed.patients}) == 22
    assert len({p.bed for p in seed.patients}) == 22
    assert all(p.synthetic for p in SEED_PATIENTS)


def test_seed_covers_the_matching_test_cases() -> None:
    by_mrn = {p.mrn: p for p in SEED.patients}
    khans = [p for p in SEED.patients if p.family_name == "Khan"]
    assert {p.bed for p in khans} == {"CCU-1", "CCU-8"}
    # Transferred during the stay: history ends in the current bed.
    moved = by_mrn["MRN-100014"]
    assert [loc.bed for loc in moved.locations] == ["CCU-19", "CCU-14"]
    assert moved.locations[-1].days_ago_end is None
    # Every patient carries the clinical picture.
    for p in SEED.patients:
        assert p.problems and p.medications and p.labs, p.mrn
    assert by_mrn["MRN-100015"].code_status == CodeStatus.dnr
    assert (
        by_mrn["MRN-100017"].labs[0].interpretation
        == ObservationInterpretation.critical_low
    )


def test_seed_file_rejects_shared_beds_and_broken_bed_history() -> None:
    first, second = (p.model_dump(mode="json") for p in SEED.patients[:2])
    second["bed"] = first["bed"]
    with pytest.raises(ValidationError, match="share a bed"):
        SeedFile.model_validate({"unit": "CCU", "patients": [first, second]})

    first["locations"] = [{"bed": "CCU-99", "days_ago_start": 1}]
    with pytest.raises(ValidationError, match="open row"):
        SeedFile.model_validate({"unit": "CCU", "patients": [first]})
