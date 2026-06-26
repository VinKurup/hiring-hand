# resume-booster

A local tool for **maximizing your own chances at a job**. Point it at your résumé
and several job descriptions for the kind of role you're targeting, and it tells you
where you fall short and exactly what to build, show, or learn to close the gap —
including GitHub-profile work.

It's an inversion of HackerRank's [interviewstreet/hiring-agent](https://github.com/interviewstreet/hiring-agent):
that project scores a candidate *for a recruiter*; resume-booster runs the same kind
of analysis *for you, the candidate*, and turns the gaps into a ranked action plan.

## How it works

A staged pipeline, each stage cached so tweaking a later step doesn't re-run the
expensive earlier ones:

1. **parse résumé** — PDF → structured JSON Resume (reused from upstream).
2. **enrich GitHub** — fetch + classify your repos (reused from upstream).
3. **build role profile** — read all your pasted job descriptions together and extract
   the *recurring* must-haves. Frequency across postings is what stops it from
   overfitting to one company's wishlist.
4. **match** — score your résumé + GitHub as **evidence** against that profile. Two
   scores model the two screening gates:
   - **visibility** (recruiter / ATS skim): can a coarse filter see the must-haves you
     genuinely have?
   - **evidence** (hiring manager): is there real depth — impact, scope, level?

   It also flags **claim-without-evidence** gaps (résumé claims X, nothing backs it up).
5. **recommend** — turn weak/missing must-haves into a ranked plan in three buckets:
   **build** (scoped project ideas), **github** (pin/README/contribution fixes), and
   **learn** (skills/tools by score impact). Honesty rule: an unbacked claim becomes
   "go build/show evidence," never "add this keyword."

## Setup

**Backend** (Python 3.12 — note: 3.13/3.14 lack a `pydantic-core` wheel):

    python3.12 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    cp .env.example .env      # then set OPENAI_API_KEY (+ optional DEFAULT_MODEL, GITHUB_TOKEN)

The LLM layer supports Ollama, Gemini, or any OpenAI-compatible endpoint (OpenRouter,
OpenAI, …) — select with `LLM_PROVIDER` / `DEFAULT_MODEL` in `.env`.

**Frontend** (Node + yarn):

    cd frontend && yarn

## Running

### CLI (quickest)

    .venv/bin/python run_pipeline.py path/to/resume.pdf jd1.txt jd2.txt

Prints the role profile, the two gate scores, and the recommendations as JSON. Stage
output is cached under `.pipeline_cache/`.

### API

    .venv/bin/uvicorn api:app --reload --port 8000

- `POST /resumes` (multipart `file=<pdf>`) — upload + parse a résumé
- `POST /jobs` `{ "label", "description" }` — add a job description
- `PATCH /jobs/{id}` `{ "included": false }` — include/exclude a job from the set
- `POST /evaluations` `{ "resume_id": 1 }` — run the pipeline over included jobs
- `GET /evaluations?resume_id=1` — evaluation history for a résumé

Interactive docs at `http://localhost:8000/docs`. The SQLite DB is `resume_booster.db`;
uploaded PDFs go to `uploads/`.

### Web UI

Two processes. Backend (repo root):

    .venv/bin/uvicorn api:app --reload --port 8000

Frontend (in `frontend/`):

    yarn dev

Open the printed URL (default http://localhost:5173). Vite proxies `/api/*` to the
backend on :8000. Flow: upload a résumé on **Resume**, paste several postings for the
same role on **Jobs** (keep the ones to target checked), then **Report** → pick the
résumé → Run evaluation.

> Tip: paste **multiple job descriptions for the same role class**. The frequency
> signal is what separates genuine must-haves from one posting's noise.

## Tests

    .venv/bin/python -m pytest -q        # backend
    cd frontend && yarn test             # frontend

## Tech stack

- **Backend:** Python, FastAPI, SQLModel + SQLite, Pydantic, PyMuPDF, Jinja.
- **Frontend:** Vite, React, TypeScript, react-router, Tailwind, Vitest.

## Credits

This project is a fork-and-extend of **[interviewstreet/hiring-agent](https://github.com/interviewstreet/hiring-agent)**
by HackerRank, which is MIT-licensed. The résumé-reading half — PDF parsing
(`pdf.py`, `pymupdf_rag.py`), GitHub enrichment (`github.py`), the JSON Resume schema
and transforms (`models.py`, `transform.py`), the section-extraction prompt templates,
and the LLM provider abstraction (`llm_utils.py`, `prompt.py`) — derives from that
project and retains its MIT license. The role-profile → evidence-match → recommendation
pipeline, the persistence/API layer, and the web UI are new.

Thanks to the hiring-agent authors for solving the tedious parts (PDF + GitHub) so this
project could focus on the candidate-facing analysis.
