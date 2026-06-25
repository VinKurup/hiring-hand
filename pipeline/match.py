"""Stage 4: score the resume + GitHub as evidence against the role profile."""

from typing import Optional

from match_models import RoleProfile, MatchReport
from pipeline.llm_call import call_structured
from pipeline.prompts import MATCH_SYSTEM, match_user


def match(
    role_profile: RoleProfile,
    resume_text: str,
    github_text: str,
    model: Optional[str] = None,
) -> MatchReport:
    user = match_user(role_profile, resume_text, github_text)
    return call_structured(MATCH_SYSTEM, user, MatchReport, model=model)
