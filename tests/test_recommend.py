import json
from match_models import MatchReport, MustHaveMatch
from pipeline.recommend import recommend


def _report():
    return MatchReport(
        matches=[
            MustHaveMatch(skill="Kubernetes", status="missing",
                          evidence="no k8s anywhere", claim_without_evidence=False),
            MustHaveMatch(skill="Python", status="strong",
                          evidence="5 yrs", claim_without_evidence=False),
        ],
        visibility_score=60,
        evidence_score=55,
    )


def test_recommend_returns_buckets(fake_provider_factory):
    canned = json.dumps({
        "build": [{"project": "Deploy a service on k8s", "stack": ["Go", "Kubernetes"],
                   "closes_gap": "Kubernetes"}],
        "github": [{"action": "Pin the k8s demo repo", "closes_gap": "Kubernetes"}],
        "learn": [{"skill": "Kubernetes", "score_impact": "high"}],
    })
    fake_provider_factory([canned])
    recs = recommend(_report(), model="m")
    assert recs.build[0].closes_gap == "Kubernetes"
    assert recs.learn[0].score_impact == "high"


def test_recommend_prompt_focuses_on_gaps(fake_provider_factory):
    canned = json.dumps({"build": [], "github": [], "learn": []})
    provider = fake_provider_factory([canned])
    recommend(_report(), model="m")
    user_msg = provider.calls[0]["messages"][1]["content"]
    assert "Kubernetes" in user_msg
