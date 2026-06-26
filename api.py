"""FastAPI app for resume-booster: resumes, jobs, evaluations."""

import json
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from db import get_session, init_db
from db_models import Job, Resume, EvaluationRecord, RoleProfileRecord
from service import ingest_resume, run_evaluation

UPLOAD_DIR = Path("uploads")


class JobCreate(BaseModel):
    label: str
    description: str


class JobUpdate(BaseModel):
    label: str | None = None
    description: str | None = None
    included: bool | None = None


class EvaluateRequest(BaseModel):
    resume_id: int
    model: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    UPLOAD_DIR.mkdir(exist_ok=True)
    yield


app = FastAPI(title="resume-booster", lifespan=lifespan)


# ---- resumes ----

@app.post("/resumes")
def upload_resume(file: UploadFile = File(...), session: Session = Depends(get_session)):
    UPLOAD_DIR.mkdir(exist_ok=True)
    safe_name = Path(file.filename).name
    dest = UPLOAD_DIR / safe_name
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    try:
        row = ingest_resume(safe_name, str(dest), session)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": row.id, "filename": row.filename, "created_at": row.created_at.isoformat()}


@app.get("/resumes")
def list_resumes(session: Session = Depends(get_session)):
    rows = session.exec(select(Resume)).all()
    return [
        {"id": r.id, "filename": r.filename, "created_at": r.created_at.isoformat()}
        for r in rows
    ]


@app.get("/resumes/{resume_id}")
def get_resume(resume_id: int, session: Session = Depends(get_session)):
    row = session.get(Resume, resume_id)
    if row is None:
        raise HTTPException(status_code=404, detail="resume not found")
    return {
        "id": row.id,
        "filename": row.filename,
        "parsed": json.loads(row.parsed_json),
        "created_at": row.created_at.isoformat(),
    }


# ---- jobs ----

def _job_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "label": job.label,
        "description": job.description,
        "included": job.included,
        "created_at": job.created_at.isoformat(),
    }


@app.post("/jobs")
def create_job(payload: JobCreate, session: Session = Depends(get_session)):
    job = Job(label=payload.label, description=payload.description)
    session.add(job)
    session.commit()
    session.refresh(job)
    return _job_dict(job)


@app.get("/jobs")
def list_jobs(session: Session = Depends(get_session)):
    return [_job_dict(j) for j in session.exec(select(Job)).all()]


@app.patch("/jobs/{job_id}")
def update_job(job_id: int, payload: JobUpdate, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(job, key, value)
    session.add(job)
    session.commit()
    session.refresh(job)
    return _job_dict(job)


@app.delete("/jobs/{job_id}")
def delete_job(job_id: int, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    session.delete(job)
    session.commit()
    return {"deleted": job_id}


# ---- evaluations ----

def _evaluation_dict(evaluation: EvaluationRecord, session: Session) -> dict:
    profile_row = session.get(RoleProfileRecord, evaluation.role_profile_id)
    return {
        "id": evaluation.id,
        "resume_id": evaluation.resume_id,
        "visibility_score": evaluation.visibility_score,
        "evidence_score": evaluation.evidence_score,
        "role_profile": json.loads(profile_row.profile_json) if profile_row else None,
        "match": json.loads(evaluation.match_json),
        "recommendations": json.loads(evaluation.recommendations_json),
        "created_at": evaluation.created_at.isoformat(),
    }


@app.post("/evaluations")
def create_evaluation(payload: EvaluateRequest, session: Session = Depends(get_session)):
    try:
        evaluation = run_evaluation(payload.resume_id, session, model=payload.model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _evaluation_dict(evaluation, session)


@app.get("/evaluations/{evaluation_id}")
def get_evaluation(evaluation_id: int, session: Session = Depends(get_session)):
    evaluation = session.get(EvaluationRecord, evaluation_id)
    if evaluation is None:
        raise HTTPException(status_code=404, detail="evaluation not found")
    return _evaluation_dict(evaluation, session)


@app.get("/evaluations")
def list_evaluations(resume_id: int, session: Session = Depends(get_session)):
    rows = session.exec(
        select(EvaluationRecord).where(EvaluationRecord.resume_id == resume_id)
    ).all()
    return [_evaluation_dict(r, session) for r in rows]
