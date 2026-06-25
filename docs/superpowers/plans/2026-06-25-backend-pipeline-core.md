# Backend Pipeline Core — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend pipeline for resume-booster: fork the upstream "read the inputs" plumbing, add an OpenAI-compatible LLM provider, and implement the three new stages (build_profile → match → recommend) behind a command-line runner that turns a resume PDF + pasted job descriptions into a gap report and a ranked to-do list.

**Architecture:** Fork of `interviewstreet/hiring-agent`. We keep its PDF parsing, GitHub enrichment, JSON Resume schema, extraction prompts, and provider abstraction. We add a new `pipeline/` package with three stages that each call the LLM through one shared helper, validate the result with Pydantic, and retry once on bad JSON. A CLI orchestrator wires the stages together and caches each stage's JSON output to disk so re-running a later stage doesn't re-parse the PDF or re-hit GitHub.

**Tech Stack:** Python 3.11+, Pydantic v2, PyMuPDF, Jinja2, the `ollama` / `google-generativeai` / `openai` SDKs, `pytest` for tests.

---

## File Structure

Files brought in from upstream (copied, mostly unmodified):
- `pdf.py`, `pymupdf_rag.py` — PDF → markdown text.
- `models.py` — JSON Resume schemas + provider classes + `ModelProvider` enum. **Modified** (add OpenAI-compatible provider + enum value).
- `transform.py` — normalize LLM JSON → resume schema; also has `convert_json_resume_to_text` / `convert_github_data_to_text` used by the matcher.
- `github.py` — fetch profile + repos, classify projects.
- `prompt.py` — model/provider config. **Modified** (add OpenAI-compatible routing + keys).
- `llm_utils.py` — `initialize_llm_provider` + `extract_json_from_response`. **Modified** (route to new provider).
- `config.py`, `.env.example`, `requirements.txt` — **Modified** (new deps + env).
- `prompts/` extraction templates + `template_manager.py` — used by stage 1.

New files we create:
- `match_models.py` — Pydantic models for the new stages: `RoleProfile`, `MustHave`, `MatchReport`, `MustHaveMatch`, `Recommendations`, etc.
- `pipeline/__init__.py` — package marker.
- `pipeline/prompts.py` — plain-string system/user prompts for the three new stages (new prompts are plain Python constants, not Jinja — they don't need the template_manager machinery, and this keeps them in one readable place).
- `pipeline/llm_call.py` — `call_structured()`: one place that calls the provider, strips/parses JSON, validates against a Pydantic model, retries once.
- `pipeline/build_profile.py` — stage 3.
- `pipeline/match.py` — stage 4.
- `pipeline/recommend.py` — stage 5.
- `run_pipeline.py` — CLI orchestrator with on-disk JSON stage cache.
- `tests/conftest.py` — `FakeProvider` + fixtures.
- `tests/test_*.py` — one test module per new unit.

---

## Task 1: Project skeleton + fork upstream plumbing

**Files:**
- Create: `requirements.txt`, `.gitignore`, `.env.example`, `README.md`
- Create (copied from upstream): `pdf.py`, `pymupdf_rag.py`, `models.py`, `transform.py`, `github.py`, `prompt.py`, `llm_utils.py`, `config.py`, `prompts/` (whole dir)

- [ ] **Step 1: Clone upstream into a temp dir and copy the kept files**

Run from the repo root (`/Users/vkurup/resume-booster`):

```bash
git clone --depth 1 https://github.com/interviewstreet/hiring-agent /tmp/hiring-agent-src
cp /tmp/hiring-agent-src/pdf.py \
   /tmp/hiring-agent-src/pymupdf_rag.py \
   /tmp/hiring-agent-src/models.py \
   /tmp/hiring-agent-src/transform.py \
   /tmp/hiring-agent-src/github.py \
   /tmp/hiring-agent-src/prompt.py \
   /tmp/hiring-agent-src/llm_utils.py \
   /tmp/hiring-agent-src/config.py \
   .
cp -r /tmp/hiring-agent-src/prompts .
```

We deliberately do NOT copy `evaluator.py`, `score.py`, or `prompts/templates/resume_evaluation_*.jinja` — those are the recruiter-judgment half we are replacing.

- [ ] **Step 2: Remove the recruiter-evaluation templates we won't use**

```bash
rm -f prompts/templates/resume_evaluation_criteria.jinja \
      prompts/templates/resume_evaluation_system_message.jinja
```

- [ ] **Step 3: Write `requirements.txt`**

```
PyMuPDF==1.26.3
ollama==0.5.1
pydantic==2.11.7
requests==2.32.4
pymupdf4llm==0.0.27
Jinja2==3.1.6
google-generativeai==0.4.0
openai==1.59.6
python-dotenv==1.0.1
pytest==8.3.4
black==25.9.0
```

(`openai` and `pytest` are the additions over upstream.)

- [ ] **Step 4: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.env
cache/
.pipeline_cache/
.pytest_cache/
```

- [ ] **Step 5: Write `.env.example`**

```
# LLM provider: "ollama", "gemini", or "openai"
# "openai" means any OpenAI-compatible endpoint (OpenAI, OpenRouter, etc.)
LLM_PROVIDER=openai

# Model name. For openai/OpenRouter use the gateway's model id,
# e.g. "anthropic/claude-sonnet-4.6" on OpenRouter.
DEFAULT_MODEL=anthropic/claude-sonnet-4.6

# Gemini (only if LLM_PROVIDER=gemini)
GEMINI_API_KEY=

# OpenAI-compatible (only if LLM_PROVIDER=openai)
OPENAI_API_KEY=
OPENAI_BASE_URL=https://openrouter.ai/api/v1

# Optional: raises GitHub API rate limits
GITHUB_TOKEN=
```

- [ ] **Step 6: Create venv and install**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Expected: installs without error.

- [ ] **Step 7: Verify the kept modules import**

```bash
.venv/bin/python -c "import models, transform, github, prompt, llm_utils, pdf; print('imports ok')"
```

Expected: prints `imports ok` (downloads nothing, hits no network).

- [ ] **Step 8: Commit** (draft message; user approves wording)

```bash
git add -A
git commit -m "fork upstream plumbing"
```

---

## Task 2: Add an OpenAI-compatible LLM provider

We keep Ollama and Gemini and add a third provider that talks to any OpenAI-compatible endpoint. The provider's `chat()` must return the same shape the others do: `{"message": {"role": "assistant", "content": "<text>"}}`.

**Files:**
- Modify: `models.py` (add `ModelProvider.OPENAI`, add `OpenAICompatibleProvider`)
- Modify: `prompt.py` (add `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `PROVIDER` already exists)
- Modify: `llm_utils.py` (route to the new provider)
- Test: `tests/test_openai_provider.py`

- [ ] **Step 1: Write the failing test**

`tests/test_openai_provider.py`:

```python
from unittest.mock import MagicMock, patch
from models import OpenAICompatibleProvider


def test_openai_provider_normalizes_response():
    fake_completion = MagicMock()
    fake_completion.choices = [MagicMock(message=MagicMock(content="hello world"))]

    with patch("openai.OpenAI") as OpenAIClass:
        client = OpenAIClass.return_value
        client.chat.completions.create.return_value = fake_completion

        provider = OpenAICompatibleProvider(api_key="k", base_url="http://x/v1")
        result = provider.chat(
            model="some/model",
            messages=[{"role": "user", "content": "hi"}],
            options={"temperature": 0},
        )

    assert result == {"message": {"role": "assistant", "content": "hello world"}}
    # temperature from options is forwarded
    _, kwargs = client.chat.completions.create.call_args
    assert kwargs["temperature"] == 0
    assert kwargs["model"] == "some/model"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_openai_provider.py -v`
Expected: FAIL with `ImportError: cannot import name 'OpenAICompatibleProvider'`.

- [ ] **Step 3: Add the enum value in `models.py`**

Find:

```python
class ModelProvider(Enum):
    """Enum for supported model providers."""

    OLLAMA = "ollama"
    GEMINI = "gemini"
```

Replace with:

```python
class ModelProvider(Enum):
    """Enum for supported model providers."""

    OLLAMA = "ollama"
    GEMINI = "gemini"
    OPENAI = "openai"
```

- [ ] **Step 4: Add `OpenAICompatibleProvider` in `models.py`**

Add this class directly after the `GeminiProvider` class:

```python
class OpenAICompatibleProvider:
    """Provider for any OpenAI-compatible endpoint (OpenAI, OpenRouter, etc.)."""

    def __init__(self, api_key: str, base_url: str):
        import openai

        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        options: Dict[str, Any] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Send a chat request and normalize to the shared response shape."""
        params: Dict[str, Any] = {"model": model, "messages": messages}
        if options:
            if "temperature" in options:
                params["temperature"] = options["temperature"]
            if "top_p" in options:
                params["top_p"] = options["top_p"]

        completion = self.client.chat.completions.create(**params)
        content = completion.choices[0].message.content
        return {"message": {"role": "assistant", "content": content}}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_openai_provider.py -v`
Expected: PASS.

- [ ] **Step 6: Add keys in `prompt.py`**

Find the line:

```python
# Get API keys from environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
```

Replace with:

```python
# Get API keys from environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
```

- [ ] **Step 7: Route to the new provider in `llm_utils.py`**

Replace the whole `initialize_llm_provider` function and the import line with:

```python
from models import (
    ModelProvider,
    OllamaProvider,
    GeminiProvider,
    OpenAICompatibleProvider,
)
from prompt import (
    MODEL_PROVIDER_MAPPING,
    GEMINI_API_KEY,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    PROVIDER,
)
```

```python
def initialize_llm_provider(model_name: str) -> Any:
    """
    Initialize the LLM provider for a model name.

    Resolution order: explicit MODEL_PROVIDER_MAPPING entry first; otherwise
    fall back to the LLM_PROVIDER env value (PROVIDER). This lets arbitrary
    OpenAI-compatible model ids (e.g. "anthropic/claude-sonnet-4.6") route to
    the OpenAI provider without being listed in the mapping.
    """
    mapped = MODEL_PROVIDER_MAPPING.get(model_name)
    provider_value = mapped.value if mapped else PROVIDER

    if provider_value == ModelProvider.OPENAI.value:
        if not OPENAI_API_KEY:
            logger.warning("⚠️ OPENAI_API_KEY not found. Falling back to Ollama.")
            return OllamaProvider()
        logger.info(f"🔄 Using OpenAI-compatible provider with model {model_name}")
        return OpenAICompatibleProvider(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

    if provider_value == ModelProvider.GEMINI.value:
        if not GEMINI_API_KEY:
            logger.warning("⚠️ Gemini API key not found. Falling back to Ollama.")
            return OllamaProvider()
        logger.info(f"🔄 Using Google Gemini API provider with model {model_name}")
        return GeminiProvider(api_key=GEMINI_API_KEY)

    logger.info(f"🔄 Using Ollama provider with model {model_name}")
    return OllamaProvider()
```

- [ ] **Step 8: Add a routing test**

Append to `tests/test_openai_provider.py`:

```python
def test_initialize_routes_unmapped_model_to_openai(monkeypatch):
    import llm_utils
    monkeypatch.setattr(llm_utils, "PROVIDER", "openai")
    monkeypatch.setattr(llm_utils, "OPENAI_API_KEY", "k")
    with patch("openai.OpenAI"):
        provider = llm_utils.initialize_llm_provider("anthropic/claude-sonnet-4.6")
    from models import OpenAICompatibleProvider
    assert isinstance(provider, OpenAICompatibleProvider)
```

- [ ] **Step 9: Run the provider tests**

Run: `.venv/bin/python -m pytest tests/test_openai_provider.py -v`
Expected: 2 passed.

- [ ] **Step 10: Commit** (draft message; user approves)

```bash
git add -A
git commit -m "add openai-compatible provider"
```

---

## Task 3: New Pydantic models for the pipeline

**Files:**
- Create: `match_models.py`
- Test: `tests/test_match_models.py`

- [ ] **Step 1: Write the failing test**

`tests/test_match_models.py`:

```python
import pytest
from pydantic import ValidationError
from match_models import (
    MustHave,
    RoleProfile,
    MustHaveMatch,
    MatchReport,
    Recommendations,
)


def test_role_profile_valid():
    rp = RoleProfile(
        title="Senior Backend Engineer",
        job_count=3,
        must_haves=[MustHave(skill="Python", category="tech", frequency=3)],
    )
    assert rp.must_haves[0].skill == "Python"


def test_role_profile_requires_at_least_one_must_have():
    with pytest.raises(ValidationError):
        RoleProfile(title="x", job_count=1, must_haves=[])


def test_match_report_score_bounds():
    with pytest.raises(ValidationError):
        MatchReport(
            matches=[MustHaveMatch(skill="Python", status="strong",
                                   evidence="3 yrs", claim_without_evidence=False)],
            visibility_score=101,
            evidence_score=50,
        )


def test_must_have_match_status_enum():
    with pytest.raises(ValidationError):
        MustHaveMatch(skill="x", status="excellent", evidence="y",
                      claim_without_evidence=False)


def test_recommendations_empty_buckets_allowed():
    recs = Recommendations(build=[], github=[], learn=[])
    assert recs.build == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_match_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'match_models'`.

- [ ] **Step 3: Write `match_models.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_match_models.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit** (draft message; user approves)

```bash
git add -A
git commit -m "add pipeline pydantic models"
```

---

## Task 4: Shared LLM call helper + fake provider for tests

**Files:**
- Create: `pipeline/__init__.py` (empty)
- Create: `pipeline/llm_call.py`
- Create: `tests/conftest.py`
- Test: `tests/test_llm_call.py`

- [ ] **Step 1: Create the package marker**

Create `pipeline/__init__.py` as an empty file.

- [ ] **Step 2: Write the `FakeProvider` fixture in `tests/conftest.py`**

```python
import json
import pytest


class FakeProvider:
    """Returns canned content from a queue, mimicking the chat() shape."""

    def __init__(self, responses):
        # responses: list of strings (raw assistant content) returned in order
        self._responses = list(responses)
        self.calls = []

    def chat(self, model, messages, options=None, **kwargs):
        self.calls.append({"model": model, "messages": messages, "options": options})
        content = self._responses.pop(0)
        return {"message": {"role": "assistant", "content": content}}


@pytest.fixture
def fake_provider_factory(monkeypatch):
    """Patch initialize_llm_provider in pipeline.llm_call to return a FakeProvider."""
    def _factory(responses):
        provider = FakeProvider(responses)
        import pipeline.llm_call as llm_call
        monkeypatch.setattr(llm_call, "initialize_llm_provider", lambda model: provider)
        return provider
    return _factory


def as_json(obj):
    return json.dumps(obj)
```

- [ ] **Step 3: Write the failing test**

`tests/test_llm_call.py`:

```python
import pytest
from pydantic import BaseModel
from pipeline.llm_call import call_structured


class Tiny(BaseModel):
    value: int


def test_call_structured_parses_valid_json(fake_provider_factory):
    fake_provider_factory(['{"value": 7}'])
    result = call_structured("sys", "user", Tiny, model="m")
    assert result.value == 7


def test_call_structured_strips_markdown_fence(fake_provider_factory):
    fake_provider_factory(['```json\n{"value": 9}\n```'])
    result = call_structured("sys", "user", Tiny, model="m")
    assert result.value == 9


def test_call_structured_retries_once_then_succeeds(fake_provider_factory):
    provider = fake_provider_factory(['not json', '{"value": 3}'])
    result = call_structured("sys", "user", Tiny, model="m")
    assert result.value == 3
    assert len(provider.calls) == 2


def test_call_structured_raises_after_two_failures(fake_provider_factory):
    fake_provider_factory(['nope', 'still nope'])
    with pytest.raises(ValueError, match="valid Tiny"):
        call_structured("sys", "user", Tiny, model="m")
```

- [ ] **Step 4: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_llm_call.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.llm_call'`.

- [ ] **Step 5: Write `pipeline/llm_call.py`**

```python
"""One place that calls the LLM, parses + validates JSON, and retries once."""

import json
import logging
from typing import Type, TypeVar

from pydantic import BaseModel

from llm_utils import initialize_llm_provider, extract_json_from_response
from prompt import DEFAULT_MODEL

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def call_structured(system: str, user: str, schema: Type[T], model: str = None) -> T:
    """
    Send system+user messages, expect JSON matching `schema`.
    Retries once with the parse error fed back, then raises ValueError.
    """
    model = model or DEFAULT_MODEL
    provider = initialize_llm_provider(model)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    last_err = None
    for attempt in range(2):
        response = provider.chat(model=model, messages=messages, options={"temperature": 0})
        content = response["message"]["content"]
        try:
            data = json.loads(extract_json_from_response(content))
            return schema.model_validate(data)
        except Exception as e:  # JSONDecodeError or pydantic ValidationError
            last_err = e
            logger.warning(f"call_structured attempt {attempt + 1} failed: {e}")
            messages.append({"role": "assistant", "content": content})
            messages.append({
                "role": "user",
                "content": (
                    f"That was not valid JSON for the required schema. "
                    f"Error: {e}. Return ONLY valid JSON, no prose, no code fences."
                ),
            })

    raise ValueError(
        f"LLM failed to produce valid {schema.__name__} after 2 attempts: {last_err}"
    )
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_llm_call.py -v`
Expected: 4 passed.

- [ ] **Step 7: Commit** (draft message; user approves)

```bash
git add -A
git commit -m "add structured llm call helper"
```

---

## Task 5: Stage 3 — build_profile

Aggregates the recurring must-haves across several pasted job descriptions. Frequency across jobs is the anti-overfitting signal.

**Files:**
- Create: `pipeline/prompts.py` (add `BUILD_PROFILE_SYSTEM`, `build_profile_user`)
- Create: `pipeline/build_profile.py`
- Test: `tests/test_build_profile.py`

- [ ] **Step 1: Write the failing test**

`tests/test_build_profile.py`:

```python
import json
from pipeline.build_profile import build_profile


def test_build_profile_returns_role_profile(fake_provider_factory):
    canned = json.dumps({
        "title": "Senior Backend Engineer",
        "job_count": 2,
        "must_haves": [
            {"skill": "Python", "category": "tech", "frequency": 2},
            {"skill": "Kubernetes", "category": "tech", "frequency": 1},
        ],
    })
    fake_provider_factory([canned])
    profile = build_profile(["JD one text", "JD two text"], model="m")
    assert profile.title == "Senior Backend Engineer"
    assert profile.must_haves[0].skill == "Python"


def test_build_profile_sends_all_jds_to_llm(fake_provider_factory):
    canned = json.dumps({
        "title": "X", "job_count": 2,
        "must_haves": [{"skill": "Python", "category": "tech", "frequency": 2}],
    })
    provider = fake_provider_factory([canned])
    build_profile(["FIRST_JD", "SECOND_JD"], model="m")
    user_msg = provider.calls[0]["messages"][1]["content"]
    assert "FIRST_JD" in user_msg and "SECOND_JD" in user_msg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_build_profile.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.build_profile'`.

- [ ] **Step 3: Add prompts in `pipeline/prompts.py`**

Create `pipeline/prompts.py`:

```python
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
```

- [ ] **Step 4: Write `pipeline/build_profile.py`**

```python
"""Stage 3: aggregate recurring must-haves across job descriptions."""

from typing import List

from match_models import RoleProfile
from pipeline.llm_call import call_structured
from pipeline.prompts import BUILD_PROFILE_SYSTEM, build_profile_user


def build_profile(job_descriptions: List[str], model: str = None) -> RoleProfile:
    if not job_descriptions:
        raise ValueError("build_profile requires at least one job description")
    user = build_profile_user(job_descriptions)
    return call_structured(BUILD_PROFILE_SYSTEM, user, RoleProfile, model=model)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_build_profile.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit** (draft message; user approves)

```bash
git add -A
git commit -m "add build_profile stage"
```

---

## Task 6: Stage 4 — match

Scores the resume + GitHub as evidence against the role profile, producing per-must-have status and the two gate scores.

**Files:**
- Modify: `pipeline/prompts.py` (add `MATCH_SYSTEM`, `match_user`)
- Create: `pipeline/match.py`
- Test: `tests/test_match.py`

- [ ] **Step 1: Write the failing test**

`tests/test_match.py`:

```python
import json
from match_models import RoleProfile, MustHave
from pipeline.match import match


def _profile():
    return RoleProfile(
        title="Senior Backend Engineer",
        job_count=2,
        must_haves=[MustHave(skill="Python", category="tech", frequency=2)],
    )


def test_match_returns_report(fake_provider_factory):
    canned = json.dumps({
        "matches": [
            {"skill": "Python", "status": "strong",
             "evidence": "5 yrs across 3 roles", "claim_without_evidence": False}
        ],
        "visibility_score": 80,
        "evidence_score": 65,
    })
    fake_provider_factory([canned])
    report = match(_profile(), resume_text="RESUME", github_text="GH", model="m")
    assert report.visibility_score == 80
    assert report.matches[0].status == "strong"


def test_match_includes_profile_resume_and_github_in_prompt(fake_provider_factory):
    canned = json.dumps({
        "matches": [{"skill": "Python", "status": "weak",
                     "evidence": "x", "claim_without_evidence": True}],
        "visibility_score": 10, "evidence_score": 10,
    })
    provider = fake_provider_factory([canned])
    match(_profile(), resume_text="RESUME_BLOB", github_text="GITHUB_BLOB", model="m")
    user_msg = provider.calls[0]["messages"][1]["content"]
    assert "RESUME_BLOB" in user_msg
    assert "GITHUB_BLOB" in user_msg
    assert "Python" in user_msg  # must-have from the profile
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_match.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.match'`.

- [ ] **Step 3: Add prompts in `pipeline/prompts.py`**

Append to `pipeline/prompts.py`:

```python
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
```

- [ ] **Step 4: Write `pipeline/match.py`**

```python
"""Stage 4: score the resume + GitHub as evidence against the role profile."""

from match_models import RoleProfile, MatchReport
from pipeline.llm_call import call_structured
from pipeline.prompts import MATCH_SYSTEM, match_user


def match(
    role_profile: RoleProfile,
    resume_text: str,
    github_text: str,
    model: str = None,
) -> MatchReport:
    user = match_user(role_profile, resume_text, github_text)
    return call_structured(MATCH_SYSTEM, user, MatchReport, model=model)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_match.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit** (draft message; user approves)

```bash
git add -A
git commit -m "add match stage"
```

---

## Task 7: Stage 5 — recommend

Turns the weak/missing must-haves into ranked actions in three buckets. Honesty gaps become "back this claim up," never "add this keyword."

**Files:**
- Modify: `pipeline/prompts.py` (add `RECOMMEND_SYSTEM`, `recommend_user`)
- Create: `pipeline/recommend.py`
- Test: `tests/test_recommend.py`

- [ ] **Step 1: Write the failing test**

`tests/test_recommend.py`:

```python
import json
from match_models import MatchReport, MustHaveMatch
from pipeline.recommend import recommend


def _report():
    return MatchReport(
        matches=[
            MustHaveMatch(skill="Kubernetes", status="missing",
                          evidence="no k8s anywhere", claim_without_evidence=False),
            MustHaveMatch(skill="Python", status="strong",
                          evidence="5 yrs", claim_without_evidence=False),
        ],
        visibility_score=60,
        evidence_score=55,
    )


def test_recommend_returns_buckets(fake_provider_factory):
    canned = json.dumps({
        "build": [{"project": "Deploy a service on k8s", "stack": ["Go", "Kubernetes"],
                   "closes_gap": "Kubernetes"}],
        "github": [{"action": "Pin the k8s demo repo", "closes_gap": "Kubernetes"}],
        "learn": [{"skill": "Kubernetes", "score_impact": "high"}],
    })
    fake_provider_factory([canned])
    recs = recommend(_report(), model="m")
    assert recs.build[0].closes_gap == "Kubernetes"
    assert recs.learn[0].score_impact == "high"


def test_recommend_prompt_focuses_on_gaps(fake_provider_factory):
    canned = json.dumps({"build": [], "github": [], "learn": []})
    provider = fake_provider_factory([canned])
    recommend(_report(), model="m")
    user_msg = provider.calls[0]["messages"][1]["content"]
    assert "Kubernetes" in user_msg  # the weak/missing one is surfaced
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_recommend.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.recommend'`.

- [ ] **Step 3: Add prompts in `pipeline/prompts.py`**

Append to `pipeline/prompts.py`:

```python
RECOMMEND_SYSTEM = """You turn a candidate's evidence gaps into a concrete, ranked action plan to improve their real chances at the target role. Be specific and honest.

Three buckets:
- build: scoped project ideas that would DEMONSTRATE a missing/weak must-have. Give a project name, a suggested stack, and which gap it closes.
- github: profile-level actions (pin a repo, write a README, show a language, contribute to an OSS project) that make real strengths visible or close a gap.
- learn: specific skills/tools/certs to acquire, each tagged with score_impact "high|medium|low" by how much it would move the match.

Hard rules:
- Never recommend adding keywords the candidate can't back up. For a claim_without_evidence gap, recommend BUILDING or SHOWING evidence ("back this claim up"), not rewording.
- Prioritize the highest-frequency missing/weak must-haves.

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
```

- [ ] **Step 4: Write `pipeline/recommend.py`**

```python
"""Stage 5: turn evidence gaps into a ranked build/github/learn action plan."""

from match_models import MatchReport, Recommendations
from pipeline.llm_call import call_structured
from pipeline.prompts import RECOMMEND_SYSTEM, recommend_user


def recommend(match_report: MatchReport, model: str = None) -> Recommendations:
    user = recommend_user(match_report)
    return call_structured(RECOMMEND_SYSTEM, user, Recommendations, model=model)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_recommend.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit** (draft message; user approves)

```bash
git add -A
git commit -m "add recommend stage"
```

---

## Task 8: CLI orchestrator with on-disk stage cache

Wires the stages into one runnable command. Each stage writes its JSON to `.pipeline_cache/`; a stage is skipped if its cache file exists and `--no-cache` is not set. Stages 1–2 (resume parse, GitHub) are reused from upstream via a thin adapter.

**Files:**
- Create: `run_pipeline.py`
- Test: `tests/test_run_pipeline.py`

> NOTE for the implementer: upstream `score.py` shows exactly how to call the stage-1 resume parse and stage-2 GitHub functions (`pdf.py` extraction + `github.py` fetch) and how `transform.convert_json_resume_to_text` / `convert_github_data_to_text` are produced. Read `score.py` in `/tmp/hiring-agent-src` before wiring `_load_resume_text` and `_load_github_text` below; replace the two clearly-marked adapter bodies with the real upstream calls. The new-stage wiring, caching, and tests below do not depend on those internals.

- [ ] **Step 1: Write the failing test**

`tests/test_run_pipeline.py`:

```python
import json
from pathlib import Path
import run_pipeline
from match_models import RoleProfile, MustHave, MatchReport, MustHaveMatch, Recommendations


def test_run_stages_3_to_5_end_to_end(tmp_path, monkeypatch):
    # Stub stages 1-2 so the test needs no PDF, no network.
    monkeypatch.setattr(run_pipeline, "_load_resume_text", lambda pdf: "RESUME TEXT")
    monkeypatch.setattr(run_pipeline, "_load_github_text", lambda resume_text: "GH TEXT")

    # Stub the three LLM stages with deterministic returns.
    profile = RoleProfile(title="Backend Eng", job_count=1,
                          must_haves=[MustHave(skill="Python", category="tech", frequency=1)])
    report = MatchReport(
        matches=[MustHaveMatch(skill="Python", status="strong",
                               evidence="ok", claim_without_evidence=False)],
        visibility_score=70, evidence_score=60)
    recs = Recommendations(build=[], github=[], learn=[])
    monkeypatch.setattr(run_pipeline, "build_profile", lambda jds, model=None: profile)
    monkeypatch.setattr(run_pipeline, "match", lambda p, resume_text, github_text, model=None: report)
    monkeypatch.setattr(run_pipeline, "recommend", lambda r, model=None: recs)

    jd_file = tmp_path / "jd1.txt"
    jd_file.write_text("a backend role")
    cache = tmp_path / "cache"

    result = run_pipeline.run(
        pdf_path="resume.pdf",
        jd_paths=[str(jd_file)],
        cache_dir=str(cache),
        model="m",
    )

    assert result["role_profile"]["title"] == "Backend Eng"
    assert result["match"]["visibility_score"] == 70
    assert "recommendations" in result
    # cache files were written
    assert (cache / "role_profile.json").exists()
    assert (cache / "match.json").exists()
    assert (cache / "recommendations.json").exists()


def test_cached_stage_is_reused(tmp_path, monkeypatch):
    monkeypatch.setattr(run_pipeline, "_load_resume_text", lambda pdf: "RESUME TEXT")
    monkeypatch.setattr(run_pipeline, "_load_github_text", lambda resume_text: "GH TEXT")

    cache = tmp_path / "cache"
    cache.mkdir()
    # Pre-seed a role_profile cache; build_profile must NOT be called.
    (cache / "role_profile.json").write_text(json.dumps(
        {"title": "Cached Role", "job_count": 1,
         "must_haves": [{"skill": "Go", "category": "tech", "frequency": 1}]}))

    def boom(*a, **k):
        raise AssertionError("build_profile should not run when cache exists")
    monkeypatch.setattr(run_pipeline, "build_profile", boom)

    report = MatchReport(
        matches=[MustHaveMatch(skill="Go", status="strong",
                               evidence="ok", claim_without_evidence=False)],
        visibility_score=50, evidence_score=50)
    monkeypatch.setattr(run_pipeline, "match", lambda p, resume_text, github_text, model=None: report)
    monkeypatch.setattr(run_pipeline, "recommend",
                        lambda r, model=None: Recommendations(build=[], github=[], learn=[]))

    jd_file = tmp_path / "jd1.txt"
    jd_file.write_text("role")
    result = run_pipeline.run(pdf_path="r.pdf", jd_paths=[str(jd_file)],
                              cache_dir=str(cache), model="m")
    assert result["role_profile"]["title"] == "Cached Role"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_run_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'run_pipeline'`.

- [ ] **Step 3: Write `run_pipeline.py`**

```python
"""CLI orchestrator: resume PDF + job descriptions -> gap report + action plan.

Stages cache their JSON to <cache_dir>/<stage>.json and are skipped when the
cache file already exists (unless --no-cache is passed).
"""

import argparse
import json
import os
from pathlib import Path
from typing import List, Optional

from match_models import RoleProfile, MatchReport
from pipeline.build_profile import build_profile
from pipeline.match import match
from pipeline.recommend import recommend


# ---- Stage 1 & 2 adapters (reused upstream code) ----
# Replace the bodies below with the real upstream calls (see score.py in the
# upstream clone). They are isolated here so the new stages stay testable.

def _load_resume_text(pdf_path: str) -> str:
    """Parse the resume PDF into JSON Resume, then to evidence text."""
    from pdf import parse_resume_pdf  # upstream entrypoint; confirm name in score.py
    from transform import convert_json_resume_to_text
    resume = parse_resume_pdf(pdf_path)
    return convert_json_resume_to_text(resume)


def _load_github_text(resume_text: str) -> str:
    """Fetch + classify GitHub from the username found in the resume."""
    from github import enrich_github  # upstream entrypoint; confirm name in score.py
    from transform import convert_github_data_to_text
    github_data = enrich_github(resume_text)
    return convert_github_data_to_text(github_data)


# ---- caching helper ----

def _cached(cache_dir: Path, name: str, use_cache: bool, schema, produce):
    """Return schema instance from cache if present, else produce + persist."""
    path = cache_dir / f"{name}.json"
    if use_cache and path.exists():
        return schema.model_validate_json(path.read_text())
    obj = produce()
    path.write_text(obj.model_dump_json(indent=2))
    return obj


def run(
    pdf_path: str,
    jd_paths: List[str],
    cache_dir: str = ".pipeline_cache",
    model: Optional[str] = None,
    use_cache: bool = True,
) -> dict:
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)

    resume_text = _load_resume_text(pdf_path)
    github_text = _load_github_text(resume_text)
    job_descriptions = [Path(p).read_text() for p in jd_paths]

    profile = _cached(cache, "role_profile", use_cache, RoleProfile,
                      lambda: build_profile(job_descriptions, model=model))
    report = _cached(cache, "match", use_cache, MatchReport,
                     lambda: match(profile, resume_text, github_text, model=model))
    recs = _cached(cache, "recommendations", use_cache, type(recommend.__wrapped__) if hasattr(recommend, "__wrapped__") else __import__("match_models").Recommendations,
                   lambda: recommend(report, model=model))

    return {
        "role_profile": profile.model_dump(),
        "match": report.model_dump(),
        "recommendations": recs.model_dump(),
    }


def main():
    parser = argparse.ArgumentParser(description="resume-booster pipeline")
    parser.add_argument("pdf", help="path to resume PDF")
    parser.add_argument("jds", nargs="+", help="paths to job-description text files")
    parser.add_argument("--cache-dir", default=".pipeline_cache")
    parser.add_argument("--model", default=None)
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    result = run(
        pdf_path=args.pdf,
        jd_paths=args.jds,
        cache_dir=args.cache_dir,
        model=args.model,
        use_cache=not args.no_cache,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
```

> The `type(recommend.__wrapped__) ...` expression above is deliberately replaced in Step 4 — it is a placeholder guard only so the file parses before the cleanup step. Do Step 4.

- [ ] **Step 4: Simplify the recommendations cache line**

In `run_pipeline.py`, replace the `recs = _cached(...)` block with the clean version, and add the import at the top.

At the top, change:

```python
from match_models import RoleProfile, MatchReport
```

to:

```python
from match_models import RoleProfile, MatchReport, Recommendations
```

Replace the `recs = _cached(...)` statement with:

```python
    recs = _cached(cache, "recommendations", use_cache, Recommendations,
                   lambda: recommend(report, model=model))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_run_pipeline.py -v`
Expected: 2 passed.

- [ ] **Step 6: Run the full test suite**

Run: `.venv/bin/python -m pytest -v`
Expected: all tests pass (provider, models, llm_call, build_profile, match, recommend, run_pipeline).

- [ ] **Step 7: Commit** (draft message; user approves)

```bash
git add -A
git commit -m "add cli pipeline orchestrator"
```

---

## Task 9: Wire real stages 1-2 and do one live smoke run

This is the only step that touches the network/LLM. It confirms the reused upstream entrypoints are named/called correctly.

**Files:**
- Modify: `run_pipeline.py` (`_load_resume_text`, `_load_github_text` bodies)

- [ ] **Step 1: Read upstream `score.py` and confirm the real entrypoints**

```bash
sed -n '1,200p' /tmp/hiring-agent-src/score.py
```

Identify the actual function used to (a) parse a resume PDF into a `JSONResume` and (b) fetch+classify GitHub. Update the two import lines and calls in `_load_resume_text` / `_load_github_text` to match. If a single upstream function does both parse+enrich, split its body across the two adapters so caching still works.

- [ ] **Step 2: Put a sample resume + JD in place**

```bash
mkdir -p samples
# copy any real resume PDF to samples/resume.pdf
# paste a real job description into samples/jd1.txt
```

- [ ] **Step 3: Configure `.env`**

```bash
cp .env.example .env
# set OPENAI_API_KEY and (if using OpenRouter) OPENAI_BASE_URL + DEFAULT_MODEL
```

- [ ] **Step 4: Run the pipeline live**

Run: `.venv/bin/python run_pipeline.py samples/resume.pdf samples/jd1.txt`
Expected: prints a JSON object with `role_profile`, `match` (with `visibility_score` / `evidence_score`), and `recommendations` (build/github/learn). `.pipeline_cache/` now holds three JSON files.

- [ ] **Step 5: Confirm caching works**

Run the same command again.
Expected: noticeably faster; stages 3-5 reload from `.pipeline_cache/` instead of calling the LLM. Then:

Run: `.venv/bin/python run_pipeline.py samples/resume.pdf samples/jd1.txt --no-cache`
Expected: re-runs all three stages.

- [ ] **Step 6: Commit** (draft message; user approves)

```bash
git add -A
git commit -m "wire live stages 1-2 and smoke run"
```

---

## Self-Review

**Spec coverage:**
- Fork-and-extend, keep input layer / replace judgment layer → Tasks 1, 2 (provider), new stages in 5-7. ✓
- OpenAI-compatible provider added alongside Ollama/Gemini → Task 2. ✓
- Staged pipeline with per-stage JSON cache → Task 8. ✓
- build_profile aggregates across multiple JDs (frequency) → Task 5. ✓
- match produces strong/weak/missing + claim-vs-evidence + visibility & evidence scores (the two gates) → Task 6. ✓
- recommend produces build/github/learn, no keyword-stuffing, honesty gaps → Task 7. ✓
- Pydantic validation + retry-once on bad JSON → Task 4 (`call_structured`). ✓
- Tests: unit per stage with mocked LLM, schema tests, end-to-end with stubbed LLM → Tasks 3-8. ✓
- NOT in this plan (later plans): SQLite persistence, FastAPI API, React frontend. These are Plans 2 and 3. The CLI runner stands in for the app so this plan produces working, testable software on its own.

**Placeholder scan:** The one intentional placeholder (the `type(recommend.__wrapped__)...` guard in Task 8 Step 3) is explicitly removed in Task 8 Step 4. Stage 1-2 adapter bodies are marked and replaced with real upstream calls in Task 9 against `score.py`. No other TBDs.

**Type consistency:** `call_structured(system, user, schema, model)` is used identically in all three stages. `build_profile(job_descriptions, model)`, `match(role_profile, resume_text, github_text, model)`, `recommend(match_report, model)` signatures match their tests and their call sites in `run_pipeline.run`. Model names (`RoleProfile`, `MatchReport`, `Recommendations`, `MustHave`, `MustHaveMatch`) are consistent across `match_models.py`, the stages, and the tests.
