"""Synthetic cardiology census for local development and demos.

Data lives in `patients.json` next to this file. All names, MRNs, dates and
results are fabricated. No real PHI. Every seeded patient is marked
`synthetic=True`.

`seed_patients` is safe to re-run: patients are upserted by MRN and each
seeded patient's clinical rows (problems, medications, allergies,
observations, bed history) are replaced wholesale. That hard replace is a
seed-only shortcut on synthetic rows; nothing else in the system hard-deletes
clinical data.
"""

import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, Field, model_validator
from sqlmodel import Session, col, select

from app.models import (
    AllergyIntolerance,
    AllergySeverity,
    CodeStatus,
    Condition,
    MedicationStatement,
    MedicationStatus,
    Observation,
    ObservationCategory,
    ObservationInterpretation,
    Patient,
    PatientCreate,
    PatientLocation,
    Sex,
)

logger = logging.getLogger(__name__)

SEED_FILE = Path(__file__).with_name("patients.json")

# Lab codes used in the seed file → display name. Production maps to LOINC.
LAB_DISPLAY = {
    "potassium": "Potassium",
    "magnesium": "Magnesium",
    "sodium": "Sodium",
    "creatinine": "Creatinine",
    "troponin": "High-sensitivity troponin I",
    "bnp": "NT-proBNP",
    "inr": "INR",
    "aptt": "aPTT",
    "crp": "C-reactive protein",
    "lactate": "Lactate",
    "tsh": "TSH",
    "haemoglobin": "Haemoglobin",
}

VITAL_DISPLAY = {
    "heart_rate": ("Heart rate", "/min"),
    "blood_pressure": ("Blood pressure", "mmHg"),
    "respiratory_rate": ("Respiratory rate", "/min"),
    "spo2": ("Oxygen saturation", "%"),
    "temperature": ("Temperature", "degC"),
}


class SeedMedication(BaseModel):
    medication: str
    dose: str
    route: str
    frequency: str
    status: MedicationStatus = MedicationStatus.active
    note: str | None = None


class SeedAllergy(BaseModel):
    substance: str
    reaction: str | None = None
    severity: AllergySeverity = AllergySeverity.unknown


class SeedVitals(BaseModel):
    hours_ago: float
    heart_rate: int
    blood_pressure: str
    respiratory_rate: int
    spo2: int
    temperature: float
    interpretations: dict[str, ObservationInterpretation] = Field(default_factory=dict)


class SeedLab(BaseModel):
    code: str
    value: float
    unit: str
    interpretation: ObservationInterpretation = ObservationInterpretation.normal
    hours_ago: float

    @model_validator(mode="after")
    def _known_code(self) -> "SeedLab":
        if self.code not in LAB_DISPLAY:
            raise ValueError(f"unknown lab code {self.code!r}")
        return self


class SeedLocation(BaseModel):
    bed: str
    days_ago_start: float
    days_ago_end: float | None = None


class SeedPatient(BaseModel):
    mrn: str
    family_name: str
    given_name: str
    birth_date: date
    sex: Sex
    bed: str
    admitting_diagnosis: str
    attending_name: str
    admitted_days_ago: float
    code_status: CodeStatus = CodeStatus.full_code
    problems: list[str]
    medications: list[SeedMedication]
    allergies: list[SeedAllergy]
    vitals: SeedVitals
    labs: list[SeedLab]
    # Bed history; omitted = one stay in the current bed since admission.
    locations: list[SeedLocation] = Field(default_factory=list)

    @model_validator(mode="after")
    def _history_ends_in_current_bed(self) -> "SeedPatient":
        if self.locations:
            open_rows = [loc for loc in self.locations if loc.days_ago_end is None]
            if len(open_rows) != 1 or open_rows[0].bed != self.bed:
                raise ValueError(
                    f"{self.mrn}: bed history must end with one open row in {self.bed}"
                )
        return self


class SeedFile(BaseModel):
    unit: str
    patients: list[SeedPatient]

    @model_validator(mode="after")
    def _unique_mrn_and_bed(self) -> "SeedFile":
        mrns = [p.mrn for p in self.patients]
        beds = [p.bed for p in self.patients]
        if len(set(mrns)) != len(mrns):
            raise ValueError("duplicate MRN in seed")
        if len(set(beds)) != len(beds):
            raise ValueError("two seed patients share a bed")
        return self


def load_seed() -> SeedFile:
    return SeedFile.model_validate_json(SEED_FILE.read_text())


def _ago(*, days: float = 0, hours: float = 0, now: datetime) -> datetime:
    return now - timedelta(days=days, hours=hours)


def _patient_create(seed: SeedPatient, unit: str, now: datetime) -> PatientCreate:
    return PatientCreate(
        mrn=seed.mrn,
        family_name=seed.family_name,
        given_name=seed.given_name,
        birth_date=seed.birth_date,
        sex=seed.sex,
        bed=seed.bed,
        unit=unit,
        admitting_diagnosis=seed.admitting_diagnosis,
        attending_name=seed.attending_name,
        admitted_at=_ago(days=seed.admitted_days_ago, now=now),
        code_status=seed.code_status,
        synthetic=True,
    )


SEED = load_seed()
UNIT = SEED.unit
_LOADED_AT = datetime.now(UTC)
# Census without a database (developer tool, evals, tests).
SEED_PATIENTS: list[PatientCreate] = [
    _patient_create(p, UNIT, _LOADED_AT) for p in SEED.patients
]


def _clinical_rows(
    seed: SeedPatient, patient_id: uuid.UUID, unit: str, now: datetime
) -> list[object]:
    admitted_at = _ago(days=seed.admitted_days_ago, now=now)
    rows: list[object] = []
    rows += [
        Condition(patient_id=patient_id, text=text, recorded_at=admitted_at)
        for text in seed.problems
    ]
    rows += [
        MedicationStatement(
            patient_id=patient_id,
            medication=m.medication,
            dose=m.dose,
            route=m.route,
            frequency=m.frequency,
            status=m.status,
            note=m.note,
            started_at=admitted_at,
        )
        for m in seed.medications
    ]
    rows += [
        AllergyIntolerance(
            patient_id=patient_id,
            substance=a.substance,
            reaction=a.reaction,
            severity=a.severity,
        )
        for a in seed.allergies
    ]
    vitals_at = _ago(hours=seed.vitals.hours_ago, now=now)
    for code, (display, unit_label) in VITAL_DISPLAY.items():
        raw = getattr(seed.vitals, code)
        rows.append(
            Observation(
                patient_id=patient_id,
                category=ObservationCategory.vital_signs,
                code=code,
                display=display,
                value=None if isinstance(raw, str) else float(raw),
                value_text=raw if isinstance(raw, str) else None,
                unit=unit_label,
                interpretation=seed.vitals.interpretations.get(
                    code, ObservationInterpretation.normal
                ),
                effective_at=vitals_at,
            )
        )
    rows += [
        Observation(
            patient_id=patient_id,
            category=ObservationCategory.laboratory,
            code=lab.code,
            display=LAB_DISPLAY[lab.code],
            value=lab.value,
            unit=lab.unit,
            interpretation=lab.interpretation,
            effective_at=_ago(hours=lab.hours_ago, now=now),
        )
        for lab in seed.labs
    ]
    locations = seed.locations or [
        SeedLocation(bed=seed.bed, days_ago_start=seed.admitted_days_ago)
    ]
    rows += [
        PatientLocation(
            patient_id=patient_id,
            bed=loc.bed,
            unit=unit,
            start_at=_ago(days=loc.days_ago_start, now=now),
            end_at=None
            if loc.days_ago_end is None
            else _ago(days=loc.days_ago_end, now=now),
        )
        for loc in locations
    ]
    return rows


CLINICAL_TABLES = (
    Condition,
    MedicationStatement,
    AllergyIntolerance,
    Observation,
    PatientLocation,
)


def seed_patients(session: Session) -> int:
    """Upsert the seed census by MRN and replace each patient's clinical rows.

    Returns the number of patients inserted (updated ones are logged).
    """
    now = datetime.now(UTC)
    inserted = updated = 0
    for seed in SEED.patients:
        patient_in = _patient_create(seed, UNIT, now)
        patient = session.exec(select(Patient).where(Patient.mrn == seed.mrn)).first()
        if patient is None:
            patient = Patient.model_validate(patient_in)
            session.add(patient)
            inserted += 1
        else:
            patient.sqlmodel_update(patient_in.model_dump(exclude={"active"}))
            session.add(patient)
            updated += 1
        session.flush()  # patient.id is needed for the child rows
        for table in CLINICAL_TABLES:
            stale = session.exec(
                select(table).where(col(table.patient_id) == patient.id)
            ).all()
            for row in stale:
                session.delete(row)
        session.add_all(_clinical_rows(seed, patient.id, UNIT, now))
    session.commit()
    logger.info("Seeded patients: %d inserted, %d updated", inserted, updated)
    return inserted
