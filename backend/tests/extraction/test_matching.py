from app.extraction.matching import match_mention
from app.extraction.schema import PatientMention
from app.models import MatchStatus, Patient


def _patient(mrn: str, given: str, family: str, bed: str) -> Patient:
    return Patient(mrn=mrn, given_name=given, family_name=family, bed=bed)


IMRAN_KHAN = _patient("MRN-100001", "Imran", "Khan", "CCU-1")
SANA_QURESHI = _patient("MRN-100006", "Sana", "Qureshi", "CCU-6")
MIRZA_BAIG = _patient("MRN-100007", "Mirza", "Baig", "CCU-7")
ZUBAIDA_KHAN = _patient("MRN-100008", "Zubaida", "Khan", "CCU-8")
CENSUS = [IMRAN_KHAN, SANA_QURESHI, MIRZA_BAIG, ZUBAIDA_KHAN]


def test_bed_exact_matches_despite_unit_prefix() -> None:
    result = match_mention(PatientMention(bed="7", verbatim="Bed 7"), CENSUS)
    assert result.status == MatchStatus.matched
    assert result.patient_id == MIRZA_BAIG.id
    assert [c.reason for c in result.candidates] == ["bed exact"]


def test_bed_spoken_with_word_bed_still_matches() -> None:
    result = match_mention(PatientMention(bed="Bed 7", verbatim="Bed 7"), CENSUS)
    assert result.status == MatchStatus.matched
    assert result.patient_id == MIRZA_BAIG.id


def test_bed_one_does_not_match_bed_ten() -> None:
    census = [*CENSUS, _patient("MRN-100010", "Rukhsana", "Chaudhry", "CCU-10")]
    result = match_mention(PatientMention(bed="1", verbatim="Bed 1"), census)
    assert result.status == MatchStatus.matched
    assert result.patient_id == IMRAN_KHAN.id


def test_mrn_exact_matches() -> None:
    result = match_mention(
        PatientMention(mrn="mrn-100006", verbatim="MRN 100006"), CENSUS
    )
    assert result.status == MatchStatus.matched
    assert result.patient_id == SANA_QURESHI.id


def test_name_fuzzy_single_hit_matches() -> None:
    result = match_mention(
        PatientMention(name="Mr. Kureshi", verbatim="Mr. Kureshi"), CENSUS
    )
    assert result.status == MatchStatus.matched
    assert result.patient_id == SANA_QURESHI.id
    assert result.candidates[0].reason == "name fuzzy"
    assert 0.85 <= result.candidates[0].score < 1.0


def test_surname_shared_by_two_patients_is_ambiguous() -> None:
    result = match_mention(PatientMention(name="Mr Khan", verbatim="Mr Khan"), CENSUS)
    assert result.status == MatchStatus.ambiguous
    assert result.patient_id is None
    assert {c.patient_id for c in result.candidates} == {IMRAN_KHAN.id, ZUBAIDA_KHAN.id}


def test_full_name_disambiguates_shared_surname() -> None:
    result = match_mention(
        PatientMention(name="Zubaida Khan", verbatim="Zubaida Khan"), CENSUS
    )
    assert result.status == MatchStatus.matched
    assert result.patient_id == ZUBAIDA_KHAN.id


def test_unknown_name_is_unmatched() -> None:
    result = match_mention(
        PatientMention(name="Mr. Smith", verbatim="Mr. Smith"), CENSUS
    )
    assert result.status == MatchStatus.unmatched
    assert result.candidates == []


def test_bed_and_name_agreeing_is_matched_with_both_reasons() -> None:
    mention = PatientMention(bed="7", name="Mr Baig", verbatim="Bed 7, Mr Baig")
    result = match_mention(mention, CENSUS)
    assert result.status == MatchStatus.matched
    assert result.patient_id == MIRZA_BAIG.id
    assert result.candidates[0].reason == "bed exact, name fuzzy"


def test_bed_and_name_disagreeing_is_ambiguous() -> None:
    mention = PatientMention(bed="7", name="Mr Khan", verbatim="Bed 7, Mr Khan")
    result = match_mention(mention, CENSUS)
    assert result.status == MatchStatus.ambiguous
    assert result.patient_id is None
    assert {c.patient_id for c in result.candidates} == {
        MIRZA_BAIG.id,
        IMRAN_KHAN.id,
        ZUBAIDA_KHAN.id,
    }


def test_bed_hit_with_unknown_name_is_ambiguous_not_silently_matched() -> None:
    mention = PatientMention(bed="7", name="Mr Smith", verbatim="Bed 7, Mr Smith")
    result = match_mention(mention, CENSUS)
    assert result.status == MatchStatus.ambiguous
    assert [c.patient_id for c in result.candidates] == [MIRZA_BAIG.id]


def test_mention_without_cues_is_unmatched() -> None:
    result = match_mention(
        PatientMention(verbatim="the gentleman by the window"), CENSUS
    )
    assert result.status == MatchStatus.unmatched


def test_candidates_serialise_for_jsonb_column() -> None:
    result = match_mention(PatientMention(bed="7", verbatim="Bed 7"), CENSUS)
    dumped = [c.model_dump(mode="json") for c in result.candidates]
    assert dumped == [
        {"patient_id": str(MIRZA_BAIG.id), "reason": "bed exact", "score": 1.0}
    ]
