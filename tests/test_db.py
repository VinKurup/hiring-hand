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


def test_init_db_creates_tables(tmp_path, monkeypatch):
    import db
    from sqlmodel import create_engine, inspect
    test_engine = create_engine(f"sqlite:///{tmp_path/'t.db'}",
                                connect_args={"check_same_thread": False})
    monkeypatch.setattr(db, "engine", test_engine)
    db.init_db()
    table_names = set(inspect(test_engine).get_table_names())
    assert {"resume", "job", "githubsnapshot", "roleprofilerecord",
            "evaluationrecord"} <= table_names


def test_get_session_yields_session():
    import db
    from sqlmodel import Session
    gen = db.get_session()
    session = next(gen)
    assert isinstance(session, Session)
    gen.close()
