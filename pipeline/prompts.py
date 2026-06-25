"""System/user prompts for the new pipeline stages (plain strings, not Jinja)."""

BUILD_PROFILE_SYSTEM = """You analyze several job descriptions for the SAME kind of role and extract the recurring requirements that define the role class.

Rules:
- Only output requirements that actually appear in the provided job descriptions. Do not invent.
- Count frequency = the number of the provided job descriptions that mention each requirement.
- Prefer requirements that recur across multiple postings; they define the role, not one company's wishlist.
- Categorize each as one of: "tech" (languages/tools/frameworks), "domain" (industry/problem area), "seniority" (level/years/leadership), "qualification" (degree/cert/clearance).

Return ONLY JSON matching this schema:
{"title": str, "job_count": int, "must_haves": [{"skill": str, "category": "tech|domain|seniority|qualification", "frequency": int}]}"""


def build_profile_user(job_descriptions):
    parts = [f"--- JOB DESCRIPTION {i + 1} ---\n{jd}" for i, jd in enumerate(job_descriptions)]
    return (
        f"There are {len(job_descriptions)} job descriptions below for the same kind of role. "
        f"Extract the role profile.\n\n" + "\n\n".join(parts)
    )
