"""Service layer: orchestrate the pipeline stages and persist to SQLite.

Stage functions and ingestion helpers are imported at module level so tests can
monkeypatch them (service.build_profile, service.load_resume, etc.).
"""

from typing import Optional

from sqlmodel import Session, select

from db_models import (
    Resume,
    GithubSnapshot,
    Job,
    RoleProfileRecord,
    EvaluationRecord,
)
from ingest import load_resume, resume_to_text, github_to_text
from pipeline.build_profile import build_profile
from pipeline.match import match
from pipeline.recommend import recommend


def ingest_resume(filename: str, pdf_path: str, session: Session) -> Resume:
    """Parse the PDF + fetch GitHub once, persist Resume + GithubSnapshot."""
    resume_obj = load_resume(pdf_path)
    if resume_obj is None:
        raise ValueError(f"Could not parse resume PDF: {pdf_path}")
    resume_text = resume_to_text(resume_obj)
    github_text = github_to_text(resume_obj)

    row = Resume(
        filename=filename,
        pdf_path=pdf_path,
        parsed_json=resume_obj.model_dump_json(),
        resume_text=resume_text,
    )
    session.add(row)
    session.commit()
    session.refresh(row)

    session.add(GithubSnapshot(resume_id=row.id, github_text=github_text))
    session.commit()
    return row


def run_evaluation(resume_id: int, session: Session, model: Optional[str] = None) -> EvaluationRecord:
    """Run build_profile -> match -> recommend over the included jobs; persist."""
    resume = session.get(Resume, resume_id)
    if resume is None:
        raise ValueError(f"No resume with id {resume_id}")

    snapshot = session.exec(
        select(GithubSnapshot).where(GithubSnapshot.resume_id == resume_id)
    ).first()
    github_text = snapshot.github_text if snapshot else ""

    jobs = session.exec(select(Job).where(Job.included == True)).all()  # noqa: E712
    if not jobs:
        raise ValueError("No jobs marked included to evaluate against")
    descriptions = [j.description for j in jobs]

    profile = build_profile(descriptions, model=model)
    profile_row = RoleProfileRecord(
        profile_json=profile.model_dump_json(),
        job_ids_csv=",".join(str(j.id) for j in jobs),
    )
    session.add(profile_row)
    session.commit()
    session.refresh(profile_row)

    report = match(profile, resume.resume_text, github_text, model=model)
    recs = recommend(report, model=model)

    evaluation = EvaluationRecord(
        resume_id=resume_id,
        role_profile_id=profile_row.id,
        match_json=report.model_dump_json(),
        recommendations_json=recs.model_dump_json(),
        visibility_score=report.visibility_score,
        evidence_score=report.evidence_score,
    )
    session.add(evaluation)
    session.commit()
    session.refresh(evaluation)
    return evaluation
