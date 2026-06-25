import pytest
from pydantic import ValidationError
from match_models import (
    MustHave,
    RoleProfile,
    MustHaveMatch,
    MatchReport,
    Recommendations,
)


def test_role_profile_valid():
    rp = RoleProfile(
        title="Senior Backend Engineer",
        job_count=3,
        must_haves=[MustHave(skill="Python", category="tech", frequency=3)],
    )
    assert rp.must_haves[0].skill == "Python"


def test_role_profile_requires_at_least_one_must_have():
    with pytest.raises(ValidationError):
        RoleProfile(title="x", job_count=1, must_haves=[])


def test_match_report_score_bounds():
    with pytest.raises(ValidationError):
        MatchReport(
            matches=[MustHaveMatch(skill="Python", status="strong",
                                   evidence="3 yrs", claim_without_evidence=False)],
            visibility_score=101,
            evidence_score=50,
        )


def test_must_have_match_status_enum():
    with pytest.raises(ValidationError):
        MustHaveMatch(skill="x", status="excellent", evidence="y",
                      claim_without_evidence=False)


def test_recommendations_empty_buckets_allowed():
    recs = Recommendations(build=[], github=[], learn=[])
    assert recs.build == []
