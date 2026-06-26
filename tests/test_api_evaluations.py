import service
from match_models import (
    RoleProfile, MustHave, MatchReport, MustHaveMatch, Recommendations,
)


def _seed_resume_and_job(client, monkeypatch):
    class _FakeResumeObj:
        def model_dump_json(self):
            return '{"basics": {"name": "Test"}}'
    monkeypatch.setattr(service, "load_resume", lambda p: _FakeResumeObj())
    monkeypatch.setattr(service, "resume_to_text", lambda r: "RESUME TEXT")
    monkeypatch.setattr(service, "github_to_text", lambda r: "GH TEXT")
    import io
    rid = client.post(
        "/resumes",
        files={"file": ("cv.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
    ).json()["id"]
    client.post("/jobs", json={"label": "Backend", "description": "jd text"})
    return rid


def test_create_and_fetch_evaluation(client, monkeypatch):
    rid = _seed_resume_and_job(client, monkeypatch)

    profile = RoleProfile(title="Backend", job_count=1,
                          must_haves=[MustHave(skill="Python", category="tech", frequency=1)])
    report = MatchReport(
        matches=[MustHaveMatch(skill="Python", status="strong",
                               evidence="ok", claim_without_evidence=False)],
        visibility_score=75, evidence_score=66)
    recs = Recommendations(build=[], github=[], learn=[])
    monkeypatch.setattr(service, "build_profile", lambda d, model=None: profile)
    monkeypatch.setattr(service, "match", lambda p, rt, gt, model=None: report)
    monkeypatch.setattr(service, "recommend", lambda r, model=None: recs)

    resp = client.post("/evaluations", json={"resume_id": rid})
    assert resp.status_code == 200
    body = resp.json()
    assert body["visibility_score"] == 75
    assert body["evidence_score"] == 66
    assert body["match"]["matches"][0]["skill"] == "Python"
    assert body["recommendations"] == {"build": [], "github": [], "learn": []}
    assert body["role_profile"]["title"] == "Backend"

    eid = body["id"]
    fetched = client.get(f"/evaluations/{eid}").json()
    assert fetched["visibility_score"] == 75

    history = client.get(f"/evaluations?resume_id={rid}").json()
    assert len(history) == 1
    assert history[0]["id"] == eid


def test_evaluation_without_jobs_returns_422(client, monkeypatch):
    class _FakeResumeObj:
        def model_dump_json(self):
            return '{"basics": {"name": "Test"}}'
    monkeypatch.setattr(service, "load_resume", lambda p: _FakeResumeObj())
    monkeypatch.setattr(service, "resume_to_text", lambda r: "RT")
    monkeypatch.setattr(service, "github_to_text", lambda r: "GT")
    import io
    rid = client.post(
        "/resumes",
        files={"file": ("cv.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
    ).json()["id"]
    # no jobs created
    resp = client.post("/evaluations", json={"resume_id": rid})
    assert resp.status_code == 422
