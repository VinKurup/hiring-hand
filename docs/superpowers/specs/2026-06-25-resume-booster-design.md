# resume-booster — Design

**Date:** 2026-06-25
**Status:** Approved (pending spec review)

## Summary

A local web app that helps me maximize my chances at a job. I upload my resume PDF
once and paste in several job descriptions for the *kind* of role I'm targeting. The
app parses my resume, pulls my GitHub, builds a combined "role profile" of the
recurring must-haves across those jobs, scores my resume as *evidence* against that
profile, and returns a gap report plus a concrete to-do list: projects to build,
GitHub fixes, and skills to learn.

It is a fork of [`interviewstreet/hiring-agent`](https://github.com/interviewstreet/hiring-agent),
inverted: instead of "score this candidate for a recruiter," it answers "tell *me* how
to close the gap."

## Screening model (the rubric this is built around)

Mirroring a single job description is overfitting — it tunes the resume to one
posting's vocabulary and fails the next, and it creates claims the resume/GitHub can't
back up. Instead, the tool is built around the idea that screening is **two gates** that
want different things:

- **Gate 1 — recruiter/ATS filter (coarse).** Checks for must-haves: core tech,
  required years, role/level, domain. The failure mode is *"I genuinely have the
  must-have but it's buried or absent, so the coarse filter can't see it."* The fix is
  **visibility of things I actually have** — never inventing keywords.
- **Gate 2 — hiring manager (evidence).** Looks for impact, scope, and level. Does my
  background map to their problems? This is where measurable bullets, projects, and
  GitHub do the work.

Consequences for the design:
- Score against the **role class**, aggregated across the several JDs pasted — not one
  posting. Frequency across jobs is what prevents overfitting.
- Score the resume as **evidence**: for each must-have, is it shown credibly? Is it
  visible to a coarse filter? Does GitHub corroborate it, or is there a claim-vs-evidence
  gap?
- "Resume changes" means **surfacing real strengths and flagging honesty gaps**, not
  phrasing-to-match. No keyword stuffing.

## Approach

**Fork-and-extend** the original repo. Keep the parts that are tedious to get right
(PDF parsing, GitHub enrichment, the JSON Resume schema, extraction prompts) and write
the entire judgment half ourselves (role profile, matcher, recommender), because that
half is exactly what we're inverting.

The backend runs as an **explicit staged pipeline**, each stage caching its JSON output
to SQLite, so tweaking a later prompt re-runs only the later stages instead of
re-parsing the PDF or re-hitting GitHub.

## What we keep / adapt / replace from the original repo

**Keep ~as-is (the "read the inputs" half):**
- `pdf.py` + `pymupdf_rag.py` — PDF → markdown text.
- `models.py` — Pydantic JSON Resume schemas (extend with new models).
- `transform.py` — normalize loose LLM JSON into the resume schema.
- `github.py` — fetch profile + repos, classify projects.
- `prompts/templates/*.jinja` extraction templates (basics, work, education, skills,
  projects, awards, github_project_selection, system_message) + `template_manager.py` +
  `prompt.py`.

**Adapt:**
- `llm_utils.py` — currently wraps Ollama and Gemini. **Keep both providers and add an
  OpenAI-compatible provider** alongside them (covers OpenAI, OpenRouter, and most
  gateways). Provider selected by config.
- `config.py`, `.env.example`, `requirements.txt` — extend for the OpenAI-compatible
  provider and trim to the deps we keep.

**Replace (the "make a recruiter judgment" half):**
- `evaluator.py` — recruiter scoring against a fixed rubric → replaced by our
  role-profile → evidence-match → recommender stages.
- `resume_evaluation_criteria.jinja` + `resume_evaluation_system_message.jinja` →
  replaced by our role-profile / match / recommend prompts.
- `score.py` — their CLI orchestrator → replaced by our staged pipeline + FastAPI.

## Architecture

- **Backend:** Python + FastAPI.
- **Frontend:** React + Vite.
- **Storage:** SQLite.
- **LLM:** existing Ollama / Gemini providers plus a new OpenAI-compatible provider,
  selected by config.

### Staged pipeline

```
1. parse_resume   (PDF → JSON Resume)             [reused: pdf.py, transform.py, extraction prompts]
2. enrich_github  (profile + repos + classify)    [reused: github.py]
3. build_profile  (N job descriptions → role profile of must-haves)        [NEW]
4. match          (resume + github evidence  vs  role profile → scored gaps) [NEW]
5. recommend      (gaps → projects / github / skills to-do list)            [NEW]
```

Stages 1–2 run once per resume. Stages 3–5 re-run when the job set changes or a prompt
is tweaked, without re-parsing the PDF or re-hitting GitHub.

### New logic (stages 3–5)

- **build_profile:** the LLM reads all pasted JDs together and extracts the *recurring*
  must-haves — core tech, seniority signals, domain, required years — tagged by how
  often they appear across the job set. Frequency is the anti-overfitting signal.
- **match:** for each must-have, the LLM checks the resume + GitHub for credible
  *evidence* and assigns one of `strong / weak / missing`. It also flags
  **claim-vs-evidence gaps** (resume claims X, GitHub shows nothing). Two sub-scores
  mirror the two gates: **visibility** (would a coarse filter see what I genuinely
  have?) and **evidence** (is there real depth?).
- **recommend:** turns `weak` / `missing` items into ranked actions in three buckets:
  - **build** — a scoped project idea + suggested stack + which gap it closes.
  - **github** — pin/README/contribution-pattern fixes; languages to show; open source
    to contribute to.
  - **learn** — a specific skill/tool/cert, ranked by impact on the match score.
  - Honesty gaps surface as "back this claim up," never "add this word."

## Data model (SQLite)

- `resume` — parsed JSON Resume + raw extracted text.
- `github_snapshot` — fetched profile + selected/classified repos, linked to a resume.
- `job` — pasted JD text + a label, plus an "included" flag for selecting the active set.
- `role_profile` — aggregated must-haves for a given job set.
- `evaluation` — match results (per must-have status + claim-vs-evidence flags), the two
  gate sub-scores, and the recommendation buckets; linked to a resume + job set.

History is retained so the score can be tracked as recommendations are acted on.

## Frontend

Three plain, functional screens (a personal tool, not a product):

- **Resume** — upload PDF; see parsed result + GitHub snapshot.
- **Jobs** — paste / label / manage JDs; toggle which are included in the active set.
- **Report** — role profile; the must-have table (strong / weak / missing +
  claim-vs-evidence flags); the two gate scores; the ranked to-do list across build /
  github / learn.

## Error handling

- Each stage validates its LLM output with Pydantic and retries once on malformed JSON
  (reusing the repo's existing retry pattern).
- A failed stage surfaces a clear error and leaves earlier cached stages intact, so the
  pipeline can resume from the failed stage rather than from scratch.

## Testing

- Unit tests on the matcher and recommender with fixture resumes + JDs, deterministic by
  mocking the LLM provider.
- A schema-validation test per pipeline stage.
- One end-to-end run on a sample PDF with a stubbed LLM.

## Out of scope (YAGNI)

- URL/job-board scraping (paste text only).
- Multi-user / auth / hosting (local, single user).
- Resume keyword-rewording / ATS keyword stuffing (explicitly rejected above).
- Automated GitHub changes (recommendations are advisory; I act on them manually).

## Git

Commits are named/approved by the user. Proposed commit messages are drafted for
approval; nothing is committed autonomously.
