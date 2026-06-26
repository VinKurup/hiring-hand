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
