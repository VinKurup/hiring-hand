"""Stage 3: aggregate recurring must-haves across job descriptions."""

from typing import List, Optional

from match_models import RoleProfile
from pipeline.llm_call import call_structured
from pipeline.prompts import BUILD_PROFILE_SYSTEM, build_profile_user


def build_profile(
    job_descriptions: List[str], model: Optional[str] = None
) -> RoleProfile:
    if not job_descriptions:
        raise ValueError("build_profile requires at least one job description")
    user = build_profile_user(job_descriptions)
    return call_structured(BUILD_PROFILE_SYSTEM, user, RoleProfile, model=model)
