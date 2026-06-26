import pytest
from sqlmodel import SQLModel, create_engine, Session, select

import service
from db_models import Resume, GithubSnapshot, Job, EvaluationRecord, RoleProfileRecord
from match_models import RoleProfile, MustHave, MatchReport, MustHaveMatch, Recommendations


def _session():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(eng)
    return Session(eng)


class _FakeResumeObj:
    """Stands in for a parsed JSONResume; only needs model_dump_json()."""
    def model_dump_json(self):
        return '{"basics": {"name": "Test"}}'


def test_ingest_resume_persists_resume_and_github(monkeypatch):
    monkeypatch.setattr(service, "load_resume", lambda p: _FakeResumeObj())
    monkeypatch.setattr(service, "resume_to_text", lambda r: "RESUME TEXT")
    monkeypatch.setattr(service, "github_to_text", lambda r: "GH TEXT")
    with _session() as s:
        row = service.ingest_resume("cv.pdf", "uploads/cv.pdf", s)
        assert row.id is not None
        assert row.resume_text == "RESUME TEXT"
        snap = s.exec(select(GithubSnapshot).where(
            GithubSnapshot.resume_id == row.id)).first()
        assert snap.github_text == "GH TEXT"


def test_ingest_resume_raises_on_unparseable_pdf(monkeypatch):
    monkeypatch.setattr(service, "load_resume", lambda p: None)
    with _session() as s:
        with pytest.raises(ValueError, match="Could not parse resume PDF"):
            service.ingest_resume("bad.pdf", "uploads/bad.pdf", s)


def test_run_evaluation_runs_stages_and_persists(monkeypatch):
    profile = RoleProfile(title="Backend", job_count=1,
                          must_haves=[MustHave(skill="Python", category="tech", frequency=1)])
    report = MatchReport(
        matches=[MustHaveMatch(skill="Python", status="strong",
                               evidence="ok", claim_without_evidence=False)],
        visibility_score=72, evidence_score=64)
    recs = Recommendations(build=[], github=[], learn=[])
    monkeypatch.setattr(service, "build_profile", lambda descs, model=None: profile)
    monkeypatch.setattr(service, "match", lambda p, rt, gt, model=None: report)
    monkeypatch.setattr(service, "recommend", lambda r, model=None: recs)

    with _session() as s:
        r = Resume(filename="cv.pdf", pdf_path="p", parsed_json="{}", resume_text="RT")
        s.add(r); s.commit(); s.refresh(r)
        s.add(GithubSnapshot(resume_id=r.id, github_text="GT"))
        s.add(Job(label="A", description="jd a", included=True))
        s.add(Job(label="B", description="jd b", included=False))
        s.commit()

        ev = service.run_evaluation(r.id, s, model="m")
        assert ev.visibility_score == 72
        assert ev.id is not None
        rp = s.get(RoleProfileRecord, ev.role_profile_id)
        assert rp is not None
        included = s.exec(select(Job).where(Job.included == True)).all()  # noqa: E712
        assert rp.job_ids_csv == ",".join(str(j.id) for j in included)
        stored = s.exec(select(EvaluationRecord)).all()
        assert len(stored) == 1


def test_run_evaluation_raises_for_missing_resume():
    with _session() as s:
        with pytest.raises(ValueError, match="No resume with id"):
            service.run_evaluation(999, s, model="m")


def test_run_evaluation_requires_included_jobs(monkeypatch):
    with _session() as s:
        r = Resume(filename="cv.pdf", pdf_path="p", parsed_json="{}", resume_text="RT")
        s.add(r); s.commit(); s.refresh(r)
        with pytest.raises(ValueError, match="No jobs"):
            service.run_evaluation(r.id, s, model="m")
