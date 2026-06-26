"""Stage 5: turn evidence gaps into a ranked build/github/learn action plan."""

from typing import Optional

from match_models import MatchReport, Recommendations
from pipeline.llm_call import call_structured
from pipeline.prompts import RECOMMEND_SYSTEM, recommend_user


def recommend(match_report: MatchReport, model: Optional[str] = None) -> Recommendations:
    user = recommend_user(match_report)
    return call_structured(RECOMMEND_SYSTEM, user, Recommendations, model=model)
