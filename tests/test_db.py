from sqlmodel import SQLModel, create_engine, Session, select
from db_models import Resume, GithubSnapshot, Job, RoleProfileRecord, EvaluationRecord


def _mem_engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(eng)
    return eng


def test_job_roundtrip():
    eng = _mem_engine()
    with Session(eng) as s:
        s.add(Job(label="Backend role", description="JD text", included=True))
        s.commit()
        jobs = s.exec(select(Job)).all()
    assert len(jobs) == 1
    assert jobs[0].included is True
    assert jobs[0].id is not None


def test_resume_and_evaluation_roundtrip():
    eng = _mem_engine()
    with Session(eng) as s:
        r = Resume(filename="cv.pdf", pdf_path="uploads/cv.pdf",
                   parsed_json="{}", resume_text="TEXT")
        s.add(r); s.commit(); s.refresh(r)
        rid = r.id
        s.add(GithubSnapshot(resume_id=r.id, github_text="GH"))
        rp = RoleProfileRecord(profile_json="{}", job_ids_csv="1,2")
        s.add(rp); s.commit(); s.refresh(rp)
        s.add(EvaluationRecord(resume_id=r.id, role_profile_id=rp.id,
                               match_json="{}", recommendations_json="{}",
                               visibility_score=70, evidence_score=60))
        s.commit()
        evals = s.exec(select(EvaluationRecord)).all()
    assert len(evals) == 1
    assert evals[0].visibility_score == 70
    assert evals[0].resume_id == rid
