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
    parts = [
        f"--- JOB DESCRIPTION {i + 1} ---\n{jd}"
        for i, jd in enumerate(job_descriptions)
    ]
    return (
        f"There are {len(job_descriptions)} job descriptions below for the same kind of role. "
        f"Extract the role profile.\n\n" + "\n\n".join(parts)
    )


MATCH_SYSTEM = """You judge how well a candidate's resume and GitHub provide EVIDENCE for each must-have of a target role. You are not a recruiter scoring a stranger; you help the candidate see their real gaps.

For each must-have, assign:
- status: "strong" (clear, specific evidence with impact/scope), "weak" (mentioned but thin or unsupported), or "missing" (no evidence).
- evidence: cite what in the resume/GitHub supports it, or state why it's missing.
- claim_without_evidence: true if the resume claims the skill but GitHub and the bullets don't back it up.

Then assign two scores 0-100:
- visibility_score (Gate 1, coarse recruiter/ATS filter): would a skim catch the must-haves the candidate GENUINELY has? Penalize buried or absent-but-real strengths. Never reward inventing keywords.
- evidence_score (Gate 2, hiring manager): depth of real evidence — impact, scope, level.

Return ONLY JSON matching this schema:
{"matches": [{"skill": str, "status": "strong|weak|missing", "evidence": str, "claim_without_evidence": bool}], "visibility_score": int, "evidence_score": int}"""


def match_user(role_profile, resume_text, github_text):
    must_haves = "\n".join(
        f"- {m.skill} ({m.category}, in {m.frequency} postings)"
        for m in role_profile.must_haves
    )
    return (
        f"TARGET ROLE: {role_profile.title}\n\n"
        f"MUST-HAVES:\n{must_haves}\n\n"
        f"=== RESUME ===\n{resume_text}\n\n"
        f"=== GITHUB ===\n{github_text}\n\n"
        f"Judge each must-have and assign the two scores."
    )


RECOMMEND_SYSTEM = """You turn a candidate's evidence gaps into a concrete, ranked action plan to improve their real chances at the target role. Be specific and honest.

Three buckets:
- build: scoped project ideas that would DEMONSTRATE a missing/weak must-have. Give a project name, a suggested stack, and which gap it closes.
- github: profile-level actions (pin a repo, write a README, show a language, contribute to an OSS project) that make real strengths visible or close a gap.
- learn: specific skills/tools/certs to acquire, each tagged with score_impact "high|medium|low" by how much it would move the match.

Hard rules:
- Never recommend adding keywords the candidate can't back up. For a claim_without_evidence gap, recommend BUILDING or SHOWING evidence ("back this claim up"), not rewording.
- Prioritize 'missing' over 'weak' must-haves, and weight items the gate scores suggest matter most.

Return ONLY JSON matching this schema:
{"build": [{"project": str, "stack": [str], "closes_gap": str}], "github": [{"action": str, "closes_gap": str}], "learn": [{"skill": str, "score_impact": "high|medium|low"}]}"""


def recommend_user(match_report):
    lines = []
    for m in match_report.matches:
        flag = " [CLAIM WITHOUT EVIDENCE]" if m.claim_without_evidence else ""
        lines.append(f"- {m.skill}: {m.status}{flag} — {m.evidence}")
    gaps = "\n".join(lines)
    return (
        f"Match scores: visibility={match_report.visibility_score}, "
        f"evidence={match_report.evidence_score}.\n\n"
        f"Per must-have status:\n{gaps}\n\n"
        f"Produce the ranked action plan. Focus on the weak and missing items."
    )
