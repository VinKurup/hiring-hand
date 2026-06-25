import json
from match_models import RoleProfile, MustHave
from pipeline.match import match


def _profile():
    return RoleProfile(
        title="Senior Backend Engineer",
        job_count=2,
        must_haves=[MustHave(skill="Python", category="tech", frequency=2)],
    )


def test_match_returns_report(fake_provider_factory):
    canned = json.dumps({
        "matches": [
            {"skill": "Python", "status": "strong",
             "evidence": "5 yrs across 3 roles", "claim_without_evidence": False}
        ],
        "visibility_score": 80,
        "evidence_score": 65,
    })
    fake_provider_factory([canned])
    report = match(_profile(), resume_text="RESUME", github_text="GH", model="m")
    assert report.visibility_score == 80
    assert report.matches[0].status == "strong"


def test_match_includes_profile_resume_and_github_in_prompt(fake_provider_factory):
    canned = json.dumps({
        "matches": [{"skill": "Python", "status": "weak",
                     "evidence": "x", "claim_without_evidence": True}],
        "visibility_score": 10, "evidence_score": 10,
    })
    provider = fake_provider_factory([canned])
    match(_profile(), resume_text="RESUME_BLOB", github_text="GITHUB_BLOB", model="m")
    user_msg = provider.calls[0]["messages"][1]["content"]
    assert "RESUME_BLOB" in user_msg
    assert "GITHUB_BLOB" in user_msg
    assert "Python" in user_msg
