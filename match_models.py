"""Pydantic models for the resume-booster pipeline (stages 3-5)."""

from typing import List, Literal
from pydantic import BaseModel, Field


# ---- Stage 3: role profile ----

class MustHave(BaseModel):
    skill: str = Field(min_length=1, description="Required capability, tech, or qualification")
    category: Literal["tech", "domain", "seniority", "qualification"]
    frequency: int = Field(ge=1, description="How many input job descriptions mention this")


class RoleProfile(BaseModel):
    title: str = Field(min_length=1, description="Inferred common role title across the jobs")
    job_count: int = Field(ge=1, description="Number of job descriptions analyzed")
    must_haves: List[MustHave] = Field(min_length=1)


# ---- Stage 4: match ----

class MustHaveMatch(BaseModel):
    skill: str = Field(min_length=1)
    status: Literal["strong", "weak", "missing"]
    evidence: str = Field(description="What in the resume/GitHub supports this, or why it is missing")
    claim_without_evidence: bool = Field(
        description="True if the resume claims this but GitHub/bullets do not back it up"
    )


class MatchReport(BaseModel):
    matches: List[MustHaveMatch] = Field(min_length=1)
    visibility_score: int = Field(
        ge=0, le=100,
        description="Gate 1: would a coarse recruiter/ATS filter see the must-haves the candidate genuinely has",
    )
    evidence_score: int = Field(
        ge=0, le=100,
        description="Gate 2: depth of real evidence (impact, scope, level)",
    )


# ---- Stage 5: recommendations ----

class BuildRecommendation(BaseModel):
    project: str = Field(min_length=1)
    stack: List[str]
    closes_gap: str = Field(description="Which must-have(s) this project demonstrates")


class GithubRecommendation(BaseModel):
    action: str = Field(min_length=1)
    closes_gap: str


class LearnRecommendation(BaseModel):
    skill: str = Field(min_length=1)
    score_impact: Literal["high", "medium", "low"]


class Recommendations(BaseModel):
    build: List[BuildRecommendation]
    github: List[GithubRecommendation]
    learn: List[LearnRecommendation]
