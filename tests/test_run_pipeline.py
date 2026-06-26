import json
from pathlib import Path
import run_pipeline
from match_models import RoleProfile, MustHave, MatchReport, MustHaveMatch, Recommendations


def test_run_stages_3_to_5_end_to_end(tmp_path, monkeypatch):
    # Stub stages 1-2 so the test needs no PDF, no network.
    monkeypatch.setattr(run_pipeline, "_load_resume_text", lambda pdf: "RESUME TEXT")
    monkeypatch.setattr(run_pipeline, "_load_github_text", lambda resume_text: "GH TEXT")

    # Stub the three LLM stages with deterministic returns.
    profile = RoleProfile(title="Backend Eng", job_count=1,
                          must_haves=[MustHave(skill="Python", category="tech", frequency=1)])
    report = MatchReport(
        matches=[MustHaveMatch(skill="Python", status="strong",
                               evidence="ok", claim_without_evidence=False)],
        visibility_score=70, evidence_score=60)
    recs = Recommendations(build=[], github=[], learn=[])
    monkeypatch.setattr(run_pipeline, "build_profile", lambda jds, model=None: profile)
    monkeypatch.setattr(run_pipeline, "match", lambda p, resume_text, github_text, model=None: report)
    monkeypatch.setattr(run_pipeline, "recommend", lambda r, model=None: recs)

    jd_file = tmp_path / "jd1.txt"
    jd_file.write_text("a backend role")
    cache = tmp_path / "cache"

    result = run_pipeline.run(
        pdf_path="resume.pdf",
        jd_paths=[str(jd_file)],
        cache_dir=str(cache),
        model="m",
    )

    assert result["role_profile"]["title"] == "Backend Eng"
    assert result["match"]["visibility_score"] == 70
    assert "recommendations" in result
    assert (cache / "role_profile.json").exists()
    assert (cache / "match.json").exists()
    assert (cache / "recommendations.json").exists()


def test_cached_stage_is_reused(tmp_path, monkeypatch):
    monkeypatch.setattr(run_pipeline, "_load_resume_text", lambda pdf: "RESUME TEXT")
    monkeypatch.setattr(run_pipeline, "_load_github_text", lambda resume_text: "GH TEXT")

    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "role_profile.json").write_text(json.dumps(
        {"title": "Cached Role", "job_count": 1,
         "must_haves": [{"skill": "Go", "category": "tech", "frequency": 1}]}))

    def boom(*a, **k):
        raise AssertionError("build_profile should not run when cache exists")
    monkeypatch.setattr(run_pipeline, "build_profile", boom)

    report = MatchReport(
        matches=[MustHaveMatch(skill="Go", status="strong",
                               evidence="ok", claim_without_evidence=False)],
        visibility_score=50, evidence_score=50)
    monkeypatch.setattr(run_pipeline, "match", lambda p, resume_text, github_text, model=None: report)
    monkeypatch.setattr(run_pipeline, "recommend",
                        lambda r, model=None: Recommendations(build=[], github=[], learn=[]))

    jd_file = tmp_path / "jd1.txt"
    jd_file.write_text("role")
    result = run_pipeline.run(pdf_path="r.pdf", jd_paths=[str(jd_file)],
                              cache_dir=str(cache), model="m")
    assert result["role_profile"]["title"] == "Cached Role"
