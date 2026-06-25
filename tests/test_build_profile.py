import json
from pipeline.build_profile import build_profile


def test_build_profile_returns_role_profile(fake_provider_factory):
    canned = json.dumps({
        "title": "Senior Backend Engineer",
        "job_count": 2,
        "must_haves": [
            {"skill": "Python", "category": "tech", "frequency": 2},
            {"skill": "Kubernetes", "category": "tech", "frequency": 1},
        ],
    })
    fake_provider_factory([canned])
    profile = build_profile(["JD one text", "JD two text"], model="m")
    assert profile.title == "Senior Backend Engineer"
    assert profile.must_haves[0].skill == "Python"


def test_build_profile_sends_all_jds_to_llm(fake_provider_factory):
    canned = json.dumps({
        "title": "X", "job_count": 2,
        "must_haves": [{"skill": "Python", "category": "tech", "frequency": 2}],
    })
    provider = fake_provider_factory([canned])
    build_profile(["FIRST_JD", "SECOND_JD"], model="m")
    user_msg = provider.calls[0]["messages"][1]["content"]
    assert "FIRST_JD" in user_msg and "SECOND_JD" in user_msg
