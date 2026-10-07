"""Seeding against the database: upsert by MRN, clinical rows replaced."""

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import Condition, Observation, Patient, PatientLocation
from app.seed.patients import CLINICAL_TABLES, SEED, seed_patients


def _count(db: Session, table: type) -> int:
    return db.exec(select(func.count()).select_from(table)).one()


def test_seed_is_idempotent_and_refreshes_clinical_rows(db: Session) -> None:
    seed_patients(db)
    patients_before = _count(db, Patient)
    clinical_before = {t.__tablename__: _count(db, t) for t in CLINICAL_TABLES}
    assert patients_before >= 22
    assert clinical_before["observation"] > 0

    baig = db.exec(select(Patient).where(Patient.mrn == "MRN-100007")).one()
    baig.attending_name = "Dr. Someone Else"
    db.add(baig)
    db.commit()

    inserted = seed_patients(db)
    assert inserted == 0
    assert _count(db, Patient) == patients_before
    assert {t.__tablename__: _count(db, t) for t in CLINICAL_TABLES} == clinical_before
    db.refresh(baig)
    assert baig.attending_name == "Dr. Siddiqui"  # seed wins on re-run
    assert baig.synthetic is True


def test_seeded_patient_has_problems_observations_and_bed_history(
    db: Session,
) -> None:
    seed_patients(db)
    moved = db.exec(select(Patient).where(Patient.mrn == "MRN-100014")).one()
    problems = db.exec(select(Condition).where(Condition.patient_id == moved.id)).all()
    assert {c.text for c in problems} == set(
        next(p for p in SEED.patients if p.mrn == moved.mrn).problems
    )
    potassium = db.exec(
        select(Observation).where(
            Observation.patient_id == moved.id, Observation.code == "potassium"
        )
    ).one()
    assert potassium.value == 4.0 and potassium.unit == "mmol/L"
    history = db.exec(
        select(PatientLocation)
        .where(PatientLocation.patient_id == moved.id)
        .order_by(col(PatientLocation.start_at))
    ).all()
    assert [h.bed for h in history] == ["CCU-19", "CCU-14"]
    assert history[0].end_at is not None and history[1].end_at is None
    assert history[1].bed == moved.bed
