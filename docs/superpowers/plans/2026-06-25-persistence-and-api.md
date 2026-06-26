# Persistence + FastAPI API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put the working resume-booster pipeline behind a local FastAPI service backed by SQLite, so resumes, jobs, and evaluations are stored and an evaluation can be run over HTTP — without breaking the existing CLI.

**Architecture:** SQLite via SQLModel (one class is both the Pydantic model and the table). A thin `service.py` orchestrates the existing pipeline stage functions (`build_profile` → `match` → `recommend`) and persists each result as a row; the DB is the persistence layer for the API while the CLI keeps its file cache. The three stage-1/2 ingestion adapters currently living in `run_pipeline.py` are extracted into a shared `ingest.py` so both the CLI and the API use them. Endpoints run synchronously: `POST /evaluations` runs the pipeline and returns the full result.

**Tech Stack:** Python 3.11+ (venv is 3.12), FastAPI, SQLModel, Uvicorn, pytest + FastAPI TestClient (httpx). LLM stages and PDF/GitHub ingestion are mocked in tests — no network.

---

## Important environment note

The venv is at `.venv` and was built with **python3.12**. ALWAYS run via `.venv/bin/python` and `.venv/bin/python -m pytest`. Never bare `python3` (system python is 3.14, incompatible with our deps).

## File Structure

New files:
- `ingest.py` — the shared stage-1/2 ingestion functions (`load_resume`, `resume_to_text`, `github_to_text`). Extracted from `run_pipeline.py`.
- `db.py` — SQLite engine, `init_db()`, `get_session()` dependency.
- `db_models.py` — SQLModel table classes: `Resume`, `GithubSnapshot`, `Job`, `RoleProfileRecord`, `EvaluationRecord`.
- `service.py` — `ingest_resume(...)` and `run_evaluation(...)`: orchestrate stages + persist.
- `api.py` — FastAPI app, lifespan startup, and all endpoints.
- `tests/test_db.py`, `tests/test_service.py`, `tests/test_api_resumes.py`, `tests/test_api_jobs.py`, `tests/test_api_evaluations.py`.

Modified files:
- `requirements.txt` — add fastapi, sqlmodel, uvicorn, python-multipart, httpx.
- `.gitignore` — add `resume_booster.db`, `uploads/`.
- `run_pipeline.py` — replace the three inline adapter defs with re-exports from `ingest.py` (behavior and the `_load_resume` / `_load_resume_text` / `_load_github_text` names unchanged, so Plan 1 tests still pass).
- `tests/conftest.py` — add a `client` fixture (temp-DB-backed TestClient).

Reused unchanged: `match_models.py`, `pipeline/*`, the forked upstream modules.

---

## Task 1: Dependencies and gitignore

**Files:**
- Modify: `requirements.txt`
- Modify: `.gitignore`

- [ ] **Step 1: Add the new dependencies to `requirements.txt`**

Append these lines to the existing `requirements.txt` (keep all existing pins):

```
fastapi==0.115.6
sqlmodel==0.0.22
uvicorn==0.34.0
python-multipart==0.0.20
httpx==0.28.1
```

- [ ] **Step 2: Install them**

Run: `.venv/bin/pip install -r requirements.txt`
Expected: installs without error.

- [ ] **Step 3: Add DB + uploads to `.gitignore`**

Append to `.gitignore`:

```
resume_booster.db
uploads/
```

- [ ] **Step 4: Verify imports work**

Run: `.venv/bin/python -c "import fastapi, sqlmodel, uvicorn, multipart, httpx; print('deps ok')"`
Expected: prints `deps ok`.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .gitignore
git commit -m "add fastapi + sqlmodel deps"
```

---

## Task 2: Extract ingestion adapters into `ingest.py` (DRY refactor)

The three stage-1/2 adapters live in `run_pipeline.py` as `_load_resume`, `_load_resume_text`, `_load_github_text`. The API needs the same logic. Move them to `ingest.py` with public names and re-export them from `run_pipeline.py` under the old names so the existing CLI tests (which monkeypatch `run_pipeline._load_resume` etc.) keep passing.

**Files:**
- Create: `ingest.py`
- Modify: `run_pipeline.py:18-63` (replace the three adapter defs with imports)
- Test: `tests/test_ingest.py`

- [ ] **Step 1: Write the failing test**

`tests/test_ingest.py`:

```python
import ingest


def test_github_to_text_no_profile_returns_header_only(monkeypatch):
    # A resume object with no GitHub profile -> github fetch is skipped -> header only.
    class FakeBasics:
        profiles = []

    class FakeResume:
        basics = FakeBasics()

    text = ingest.github_to_text(FakeResume())
    assert "GITHUB DATA" in text  # upstream converter emits the header for {}


def test_github_to_text_handles_none_resume(monkeypatch):
    text = ingest.github_to_text(None)
    assert "GITHUB DATA" in text


def test_run_pipeline_reexports_adapters():
    import run_pipeline
    assert run_pipeline._load_resume is ingest.load_resume
    assert run_pipeline._load_resume_text is ingest.resume_to_text
    assert run_pipeline._load_github_text is ingest.github_to_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_ingest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ingest'`.

- [ ] **Step 3: Create `ingest.py`**

```python
"""Stage 1 & 2 ingestion, shared by the CLI (run_pipeline) and the API service.

Stage 1 parses the PDF into a JSONResume object; stage 2 needs that structured
object to find the GitHub profile URL. Imports are function-local so importing
this module stays side-effect free.
"""


def load_resume(pdf_path: str):
    """Parse the resume PDF into a JSONResume object (upstream PDFHandler)."""
    from pdf import PDFHandler

    return PDFHandler().extract_json_from_pdf(pdf_path)


def resume_to_text(resume) -> str:
    """Convert a JSONResume object to evidence text."""
    from transform import convert_json_resume_to_text

    return convert_json_resume_to_text(resume)


def github_to_text(resume) -> str:
    """Find the GitHub profile in the resume, fetch + classify it, to text.

    Mirrors upstream: pull profiles from resume.basics, locate the "Github"
    network, fetch via fetch_and_display_github_info(url). When no GitHub
    profile is present, fetch returns {} and the converter yields just the
    header, matching upstream's missing-profile behavior.
    """
    from github import fetch_and_display_github_info
    from transform import convert_github_data_to_text

    profiles = []
    if resume is not None and getattr(resume, "basics", None):
        profiles = resume.basics.profiles or []
    github_profile = next(
        (p for p in profiles if p.network and p.network.lower() == "github"),
        None,
    )
    github_data = (
        fetch_and_display_github_info(github_profile.url) if github_profile else {}
    )
    return convert_github_data_to_text(github_data)
```

- [ ] **Step 4: Replace the adapter defs in `run_pipeline.py`**

In `run_pipeline.py`, delete the three function definitions `_load_resume`, `_load_resume_text`, `_load_github_text` (currently lines 28-63) and the comment block above them (lines 18-25). Replace ALL of that (everything from the `# ---- Stage 1 & 2 adapters` comment through the end of `_load_github_text`) with:

```python
# ---- Stage 1 & 2 adapters (shared with the API via ingest.py) ----
# Re-exported under the old private names so callers and tests that monkeypatch
# run_pipeline._load_resume / _load_resume_text / _load_github_text keep working.
from ingest import (
    load_resume as _load_resume,
    resume_to_text as _load_resume_text,
    github_to_text as _load_github_text,
)
```

Leave the rest of `run_pipeline.py` (`_cached`, `run`, `main`) unchanged. `run()` still calls `_load_resume(...)`, `_load_resume_text(...)`, `_load_github_text(...)` — now resolving to the re-exported names.

- [ ] **Step 5: Run the ingest tests and the existing run_pipeline tests**

Run: `.venv/bin/python -m pytest tests/test_ingest.py tests/test_run_pipeline.py -v`
Expected: all pass (3 new + the existing run_pipeline tests). The run_pipeline tests monkeypatch `run_pipeline._load_resume` etc., which still works because those names are bound at module level.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: 24 passed (21 from before + 3 new), warnings unchanged.

- [ ] **Step 7: Commit**

```bash
git add ingest.py run_pipeline.py tests/test_ingest.py
git commit -m "extract ingestion into shared ingest module"
```

---

## Task 3: SQLModel tables

**Files:**
- Create: `db_models.py`
- Test: `tests/test_db.py` (models portion)

- [ ] **Step 1: Write the failing test**

`tests/test_db.py`:

```python
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
    assert evals[0].resume_id == r.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'db_models'`.

- [ ] **Step 3: Write `db_models.py`**

```python
"""SQLModel tables for resume-booster persistence.

Stage outputs are stored as JSON strings (the Pydantic models' .model_dump_json()).
Table names default to the lowercased class name: resume, githubsnapshot, job,
roleprofilerecord, evaluationrecord.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Resume(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    pdf_path: str
    parsed_json: str  # JSONResume.model_dump_json()
    resume_text: str  # evidence text from convert_json_resume_to_text
    created_at: datetime = Field(default_factory=_utcnow)


class GithubSnapshot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    resume_id: int = Field(foreign_key="resume.id", index=True)
    github_text: str
    fetched_at: datetime = Field(default_factory=_utcnow)


class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    label: str
    description: str  # the pasted job-description text
    included: bool = True
    created_at: datetime = Field(default_factory=_utcnow)


class RoleProfileRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_json: str  # RoleProfile.model_dump_json()
    job_ids_csv: str  # which job ids this profile was built from
    created_at: datetime = Field(default_factory=_utcnow)


class EvaluationRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    resume_id: int = Field(foreign_key="resume.id", index=True)
    role_profile_id: int = Field(foreign_key="roleprofilerecord.id")
    match_json: str  # MatchReport.model_dump_json()
    recommendations_json: str  # Recommendations.model_dump_json()
    visibility_score: int
    evidence_score: int
    created_at: datetime = Field(default_factory=_utcnow)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_db.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add db_models.py tests/test_db.py
git commit -m "add sqlmodel tables"
```

---

## Task 4: DB engine + session

**Files:**
- Create: `db.py`
- Test: add to `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_db.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_db.py -k "init_db or get_session" -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'db'`.

- [ ] **Step 3: Write `db.py`**

```python
"""SQLite engine, schema creation, and the FastAPI session dependency."""

from typing import Iterator

from sqlmodel import SQLModel, Session, create_engine

DATABASE_URL = "sqlite:///resume_booster.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    """Create all tables. Importing db_models registers them on SQLModel.metadata."""
    import db_models  # noqa: F401  (registers tables)

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_db.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "add db engine and session"
```

---

## Task 5: Service layer (ingest_resume + run_evaluation)

**Files:**
- Create: `service.py`
- Test: `tests/test_service.py`

- [ ] **Step 1: Write the failing test**

`tests/test_service.py`:

```python
import pytest
from sqlmodel import SQLModel, create_engine, Session, select

import service
from db_models import Resume, GithubSnapshot, Job, EvaluationRecord, RoleProfileRecord
from match_models import (
    JSONResumeStub,  # noqa: F401  (placeholder; see note)
)
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
        # a RoleProfileRecord was persisted, built from only the INCLUDED job
        rp = s.get(RoleProfileRecord, ev.role_profile_id)
        assert rp is not None
        stored = s.exec(select(EvaluationRecord)).all()
        assert len(stored) == 1


def test_run_evaluation_requires_included_jobs(monkeypatch):
    with _session() as s:
        r = Resume(filename="cv.pdf", pdf_path="p", parsed_json="{}", resume_text="RT")
        s.add(r); s.commit(); s.refresh(r)
        with pytest.raises(ValueError, match="No jobs"):
            service.run_evaluation(r.id, s, model="m")
```

NOTE: the line `from match_models import JSONResumeStub` is a mistake — DELETE that import line when writing the test. (It is called out here so you do not copy it; `match_models` has no such name.) The `_FakeResumeObj` class is what stands in for the parsed resume.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'service'` (after you removed the bad import line).

- [ ] **Step 3: Write `service.py`**

```python
"""Service layer: orchestrate the pipeline stages and persist to SQLite.

Stage functions and ingestion helpers are imported at module level so tests can
monkeypatch them (service.build_profile, service.load_resume, etc.).
"""

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


def run_evaluation(resume_id: int, session: Session, model: str = None) -> EvaluationRecord:
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_service.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add service.py tests/test_service.py
git commit -m "add service layer for ingest and evaluation"
```

---

## Task 6: FastAPI app + resume endpoints

**Files:**
- Create: `api.py`
- Modify: `tests/conftest.py` (add the `client` fixture)
- Test: `tests/test_api_resumes.py`

- [ ] **Step 1: Add the `client` fixture to `tests/conftest.py`**

Append to the existing `tests/conftest.py`:

```python
@pytest.fixture
def client(tmp_path, monkeypatch):
    """A TestClient backed by a fresh temp SQLite DB, with startup side effects
    neutralized so tests touch no real DB file or uploads dir."""
    from sqlmodel import SQLModel, create_engine, Session
    from fastapi.testclient import TestClient
    import db
    import db_models  # noqa: F401  (registers tables)
    import api

    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(test_engine)

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    # Neutralize the lifespan's real-DB init + point uploads at tmp_path.
    monkeypatch.setattr(api, "init_db", lambda: None)
    monkeypatch.setattr(api, "UPLOAD_DIR", tmp_path / "uploads")
    api.app.dependency_overrides[db.get_session] = override_get_session

    with TestClient(api.app) as test_client:
        yield test_client

    api.app.dependency_overrides.clear()
```

- [ ] **Step 2: Write the failing test**

`tests/test_api_resumes.py`:

```python
import io
import service


def test_upload_resume_persists_and_returns_id(client, monkeypatch):
    class _FakeResumeObj:
        def model_dump_json(self):
            return '{"basics": {"name": "Test"}}'

    monkeypatch.setattr(service, "load_resume", lambda p: _FakeResumeObj())
    monkeypatch.setattr(service, "resume_to_text", lambda r: "RESUME TEXT")
    monkeypatch.setattr(service, "github_to_text", lambda r: "GH TEXT")

    resp = client.post(
        "/resumes",
        files={"file": ("cv.pdf", io.BytesIO(b"%PDF-fake"), "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] >= 1
    assert body["filename"] == "cv.pdf"

    listed = client.get("/resumes").json()
    assert len(listed) == 1
    assert listed[0]["filename"] == "cv.pdf"

    detail = client.get(f"/resumes/{body['id']}").json()
    assert detail["parsed"]["basics"]["name"] == "Test"


def test_upload_unparseable_pdf_returns_422(client, monkeypatch):
    monkeypatch.setattr(service, "load_resume", lambda p: None)
    resp = client.post(
        "/resumes",
        files={"file": ("bad.pdf", io.BytesIO(b"x"), "application/pdf")},
    )
    assert resp.status_code == 422


def test_get_missing_resume_returns_404(client):
    assert client.get("/resumes/999").status_code == 404
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_api_resumes.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'api'`.

- [ ] **Step 4: Write `api.py`**

```python
"""FastAPI app for resume-booster: resumes, jobs, evaluations."""

import json
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from db import get_session, init_db
from db_models import Job, Resume, EvaluationRecord
from service import ingest_resume, run_evaluation

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
    dest = UPLOAD_DIR / file.filename
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    try:
        row = ingest_resume(file.filename, str(dest), session)
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_api_resumes.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add api.py tests/conftest.py tests/test_api_resumes.py
git commit -m "add fastapi app and resume endpoints"
```

---

## Task 7: Job endpoints

**Files:**
- Modify: `api.py` (add request models + job routes)
- Test: `tests/test_api_jobs.py`

- [ ] **Step 1: Write the failing test**

`tests/test_api_jobs.py`:

```python
def test_job_crud_flow(client):
    # create
    created = client.post("/jobs", json={"label": "Backend", "description": "JD text"})
    assert created.status_code == 200
    job = created.json()
    assert job["id"] >= 1
    assert job["included"] is True

    # list
    assert len(client.get("/jobs").json()) == 1

    # toggle included off + edit label
    patched = client.patch(f"/jobs/{job['id']}",
                           json={"included": False, "label": "Backend (paused)"})
    assert patched.status_code == 200
    assert patched.json()["included"] is False
    assert patched.json()["label"] == "Backend (paused)"

    # delete
    assert client.delete(f"/jobs/{job['id']}").status_code == 200
    assert client.get("/jobs").json() == []


def test_patch_missing_job_returns_404(client):
    assert client.patch("/jobs/999", json={"included": False}).status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_api_jobs.py -v`
Expected: FAIL (404 on POST /jobs — route doesn't exist yet).

- [ ] **Step 3: Add request models + job routes to `api.py`**

Add these request models near the top of `api.py` (after the `UPLOAD_DIR` line, before `lifespan`):

```python
class JobCreate(BaseModel):
    label: str
    description: str


class JobUpdate(BaseModel):
    label: str | None = None
    description: str | None = None
    included: bool | None = None
```

Add these routes at the end of `api.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_api_jobs.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add api.py tests/test_api_jobs.py
git commit -m "add job endpoints"
```

---

## Task 8: Evaluation endpoints

**Files:**
- Modify: `api.py` (add evaluation request model + routes)
- Test: `tests/test_api_evaluations.py`

- [ ] **Step 1: Write the failing test**

`tests/test_api_evaluations.py`:

```python
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
    recs = Recommendations(build=[], github=[],
                           learn=[])
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_api_evaluations.py -v`
Expected: FAIL (404 on POST /evaluations — route doesn't exist yet).

- [ ] **Step 3: Add evaluation request model + routes to `api.py`**

Add this request model alongside the other request models (after `JobUpdate`):

```python
class EvaluateRequest(BaseModel):
    resume_id: int
    model: str | None = None
```

Add the import of `RoleProfileRecord` to the existing `db_models` import line at the top of `api.py` so it becomes:

```python
from db_models import Job, Resume, EvaluationRecord, RoleProfileRecord
```

Add these routes at the end of `api.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_api_evaluations.py -v`
Expected: 2 passed.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass (24 from Tasks 1-2 baseline + db(4) + service(4) + api_resumes(3) + api_jobs(2) + api_evaluations(2) = 39 passed).

- [ ] **Step 6: Commit**

```bash
git add api.py tests/test_api_evaluations.py
git commit -m "add evaluation endpoints"
```

---

## Task 9: Run entrypoint + manual smoke

**Files:**
- Modify: `requirements.txt` (no change) / add a short run note to `README.md` (create if absent)
- Manual verification only (no new automated test)

- [ ] **Step 1: Add a README run section**

Create or append to `README.md`:

```markdown
## Running the API

    .venv/bin/uvicorn api:app --reload --port 8000

Then:
- `POST /resumes` (multipart `file=<pdf>`) — upload + parse a resume
- `POST /jobs` `{ "label", "description" }` — add a job description
- `PATCH /jobs/{id}` `{ "included": false }` — include/exclude a job from the set
- `POST /evaluations` `{ "resume_id": 1 }` — run the pipeline over included jobs
- `GET /evaluations?resume_id=1` — history for a resume

Interactive docs at `http://localhost:8000/docs`.

Requires `.env` with `OPENAI_API_KEY` (+ `DEFAULT_MODEL`) as in `.env.example`.
The SQLite DB is `resume_booster.db`; uploaded PDFs go to `uploads/`.
```

- [ ] **Step 2: Confirm the app boots (no LLM/network needed for startup)**

Run: `.venv/bin/python -c "import api; print('app ok:', api.app.title)"`
Expected: prints `app ok: resume-booster` and creates `resume_booster.db` is NOT triggered (init_db only runs in the lifespan on real startup, not on import).

- [ ] **Step 3: Boot the server briefly and hit the docs**

Run in one command (starts, waits, checks, stops):

```bash
.venv/bin/uvicorn api:app --port 8123 &
SERVER_PID=$!
sleep 3
curl -s -o /dev/null -w "%{http_code}" http://localhost:8123/docs
echo " <- /docs status"
curl -s -o /dev/null -w "%{http_code}" http://localhost:8123/jobs
echo " <- /jobs status (expect 200, empty list)"
kill $SERVER_PID
```

Expected: `/docs` → 200, `/jobs` → 200. A `resume_booster.db` file is created in the project root (gitignored).

- [ ] **Step 4: (Optional, with a real key) full live run through the API**

With `.env` populated and a real resume PDF:

```bash
.venv/bin/uvicorn api:app --port 8123 &
SERVER_PID=$!
sleep 3
RID=$(curl -s -F "file=@samples/Resume(FS).pdf" http://localhost:8123/resumes | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
curl -s -X POST http://localhost:8123/jobs -H 'Content-Type: application/json' \
  -d "{\"label\":\"role\",\"description\":\"$(tr '\n' ' ' < samples/jd1.txt)\"}" > /dev/null
curl -s -X POST http://localhost:8123/evaluations -H 'Content-Type: application/json' \
  -d "{\"resume_id\": $RID}" | python3 -m json.tool
kill $SERVER_PID
```

Expected: JSON with `role_profile`, `match` (+ scores), and `recommendations`. This mirrors the CLI output but persisted in `resume_booster.db`.

- [ ] **Step 5: Clean up the smoke DB and commit the README**

```bash
rm -f resume_booster.db
git add README.md
git commit -m "document running the api"
```

---

## Self-Review

**Spec coverage (data model + API for the local web app):**
- `resume` table + parsed JSON + raw text → Task 3 (`Resume`), ingested in Task 5. ✓
- `github_snapshot` → Task 3 (`GithubSnapshot`), populated in Task 5. ✓
- `job` (pasted JD, label, included flag) → Task 3 (`Job`) + Task 7 CRUD. ✓
- `role_profile` (aggregated must-haves for a job set) → Task 3 (`RoleProfileRecord`), produced in Task 5. ✓
- `evaluation` (match + scores + recommendations, linked to resume + job set) → Task 3 (`EvaluationRecord`), produced in Task 5, exposed in Task 8. ✓
- History retained so score can be tracked over time → each `POST /evaluations` inserts a new row; `GET /evaluations?resume_id=` returns history. ✓
- Synchronous execution model → `POST /evaluations` runs stages and returns the result (Task 8). ✓
- SQLModel + SQLite → Tasks 3-4. ✓
- CLI keeps working → Task 2 re-exports adapters; full suite (incl. Plan 1 tests) runs green at each task. ✓
- NOT in this plan (Plan 3): the React frontend. This plan ships a fully testable HTTP API + persistence, usable via curl / the auto-generated `/docs`.

**Placeholder scan:** One intentional anti-pattern is flagged inline in Task 5 Step 1 — the bogus `from match_models import JSONResumeStub` line is explicitly called out to be DELETED, not copied. No other TBDs; every code step is complete.

**Type consistency:** Table classes `Resume`, `GithubSnapshot`, `Job`, `RoleProfileRecord`, `EvaluationRecord` are used identically across `db_models.py`, `service.py`, `api.py`, and the tests. Service signatures `ingest_resume(filename, pdf_path, session)` and `run_evaluation(resume_id, session, model=None)` match their call sites in `api.py` and the tests. The `model` param threads through `build_profile`/`match`/`recommend` exactly as in Plan 1. FK target strings (`resume.id`, `roleprofilerecord.id`) match the default lowercased table names. The `client` fixture monkeypatches `api.init_db` and `api.UPLOAD_DIR`, both of which exist in `api.py`.
