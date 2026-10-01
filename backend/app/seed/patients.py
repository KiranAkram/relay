"""Synthetic cardiology census for local development and demos.

All names, MRNs and dates are fabricated. No real PHI.
"""

import logging
from datetime import UTC, date, datetime, timedelta

from sqlmodel import Session, col, select

from app.models import Patient, PatientCreate, Sex

logger = logging.getLogger(__name__)

UNIT = "CCU"


def _admitted(days_ago: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=days_ago)


SEED_PATIENTS: list[PatientCreate] = [
    PatientCreate(
        mrn="MRN-100001",
        family_name="Khan",
        given_name="Imran",
        birth_date=date(1958, 3, 14),
        sex=Sex.male,
        bed="CCU-1",
        unit=UNIT,
        admitting_diagnosis="NSTEMI, post-PCI to LAD (drug-eluting stent)",
        attending_name="Dr. Siddiqui",
        admitted_at=_admitted(1),
    ),
    PatientCreate(
        mrn="MRN-100002",
        family_name="Ahmed",
        given_name="Farida",
        birth_date=date(1949, 11, 2),
        sex=Sex.female,
        bed="CCU-2",
        unit=UNIT,
        admitting_diagnosis="Acute decompensated heart failure, EF 25%, on IV furosemide",
        attending_name="Dr. Siddiqui",
        admitted_at=_admitted(3),
    ),
    PatientCreate(
        mrn="MRN-100003",
        family_name="Raza",
        given_name="Bilal",
        birth_date=date(1971, 6, 27),
        sex=Sex.male,
        bed="CCU-3",
        unit=UNIT,
        admitting_diagnosis="Atrial fibrillation with RVR, on heparin drip",
        attending_name="Dr. Malik",
        admitted_at=_admitted(2),
    ),
    PatientCreate(
        mrn="MRN-100004",
        family_name="Hussain",
        given_name="Nasreen",
        birth_date=date(1963, 9, 8),
        sex=Sex.female,
        bed="CCU-4",
        unit=UNIT,
        admitting_diagnosis="Unstable angina, awaiting cardiac catheterisation",
        attending_name="Dr. Malik",
        admitted_at=_admitted(1),
    ),
    PatientCreate(
        mrn="MRN-100005",
        family_name="Sheikh",
        given_name="Tariq",
        birth_date=date(1955, 1, 19),
        sex=Sex.male,
        bed="CCU-5",
        unit=UNIT,
        admitting_diagnosis="STEMI, post-primary PCI to RCA, temporary pacing wire in situ",
        attending_name="Dr. Siddiqui",
        admitted_at=_admitted(1),
    ),
    PatientCreate(
        mrn="MRN-100006",
        family_name="Qureshi",
        given_name="Sana",
        birth_date=date(1980, 4, 30),
        sex=Sex.female,
        bed="CCU-6",
        unit=UNIT,
        admitting_diagnosis="Peripartum cardiomyopathy, EF 30%",
        attending_name="Dr. Malik",
        admitted_at=_admitted(5),
    ),
    PatientCreate(
        mrn="MRN-100007",
        family_name="Baig",
        given_name="Mirza",
        birth_date=date(1946, 7, 11),
        sex=Sex.male,
        bed="CCU-7",
        unit=UNIT,
        admitting_diagnosis="Complete heart block, awaiting permanent pacemaker",
        attending_name="Dr. Siddiqui",
        admitted_at=_admitted(2),
    ),
    PatientCreate(
        mrn="MRN-100008",
        family_name="Khan",
        given_name="Zubaida",
        birth_date=date(1952, 12, 5),
        sex=Sex.female,
        bed="CCU-8",
        unit=UNIT,
        admitting_diagnosis="Severe aortic stenosis, pre-TAVI workup",
        attending_name="Dr. Malik",
        admitted_at=_admitted(4),
    ),
    PatientCreate(
        mrn="MRN-100009",
        family_name="Iqbal",
        given_name="Asad",
        birth_date=date(1967, 2, 23),
        sex=Sex.male,
        bed="CCU-9",
        unit=UNIT,
        admitting_diagnosis="Pulmonary embolism, haemodynamically stable, on heparin drip",
        attending_name="Dr. Siddiqui",
        admitted_at=_admitted(1),
    ),
    PatientCreate(
        mrn="MRN-100010",
        family_name="Chaudhry",
        given_name="Rukhsana",
        birth_date=date(1959, 10, 16),
        sex=Sex.female,
        bed="CCU-10",
        unit=UNIT,
        admitting_diagnosis="Infective endocarditis (mitral valve), on IV antibiotics",
        attending_name="Dr. Malik",
        admitted_at=_admitted(6),
    ),
]


def seed_patients(session: Session) -> int:
    """Insert seed patients that don't exist yet (keyed on MRN). Returns count inserted."""
    existing = set(
        session.exec(
            select(Patient.mrn).where(
                col(Patient.mrn).in_([p.mrn for p in SEED_PATIENTS])
            )
        ).all()
    )
    inserted = 0
    for patient_in in SEED_PATIENTS:
        if patient_in.mrn in existing:
            continue
        session.add(Patient.model_validate(patient_in))
        inserted += 1
    session.commit()
    logger.info("Seeded %d patients (%d already present)", inserted, len(existing))
    return inserted
