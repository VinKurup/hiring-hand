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
