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

## Running the web UI

Two processes. Backend (repo root):

    .venv/bin/uvicorn api:app --reload --port 8000

Frontend (in `frontend/`):

    yarn          # first time
    yarn dev

Open the printed URL (default http://localhost:5173). Vite proxies `/api/*` to
the backend on :8000. Flow: upload a resume on **Resume**, paste several
postings for the same role on **Jobs** (keep the ones to target checked), then
**Report** → pick the resume → Run evaluation.

Frontend tests: `cd frontend && yarn vitest run`.
