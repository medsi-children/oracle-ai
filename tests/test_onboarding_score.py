from app.models.assessment import Assessment
from app.services.assessment import (
    ONBOARDING_INITIAL_SCORE_CAP,
    calculate_onboarding_initial_score,
)


def make_assessment(score: int) -> Assessment:
    return Assessment(
        subjectivity=score,
        honesty=score,
        emotional_sovereignty=score,
        cognitive_humility=score,
        empathy=score,
        summary="",
        raw={},
    )


def test_onboarding_initial_score_is_capped_below_final_mastery() -> None:
    assessments = [make_assessment(100) for _ in range(7)]

    assert calculate_onboarding_initial_score(assessments) == ONBOARDING_INITIAL_SCORE_CAP


def test_onboarding_initial_score_keeps_moderate_result() -> None:
    assessments = [make_assessment(58), make_assessment(62), make_assessment(60)]

    assert calculate_onboarding_initial_score(assessments) == 60
