"""
Utility functions for LLM providers.
"""

import logging
from typing import Any, Dict, Optional
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

logger = logging.getLogger(__name__)


def extract_json_from_response(response_text: str) -> str:
    """
    Extract JSON content from markdown code blocks.

    Args:
        response_text: Text that may contain JSON wrapped in markdown code blocks

    Returns:
        Text with markdown code block syntax removed
    """

    response_text = response_text.strip()
    if "<think>" in response_text:
        think_start = response_text.find("<think>")
        think_end = response_text.find("</think>")
        if think_start != -1 and think_end != -1:
            response_text = response_text[:think_start] + response_text[think_end + 8 :]

    # Remove leading ```json if present
    if response_text.startswith("```json"):
        response_text = response_text[7:]
    # Remove trailing ``` if present
    if response_text.endswith("```"):
        response_text = response_text[:-3]
    return response_text


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
