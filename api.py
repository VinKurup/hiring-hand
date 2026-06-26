"""FastAPI app for resume-booster: resumes, jobs, evaluations."""

import json
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from sqlmodel import Session, select

from db import get_session, init_db
from db_models import Resume
from service import ingest_resume

UPLOAD_DIR = Path("uploads")


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
