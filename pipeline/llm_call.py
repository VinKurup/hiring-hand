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
