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


def test_initialize_routes_unmapped_model_to_openai(monkeypatch):
    import llm_utils
    monkeypatch.setattr(llm_utils, "PROVIDER", "openai")
    monkeypatch.setattr(llm_utils, "OPENAI_API_KEY", "k")
    with patch("openai.OpenAI"):
        provider = llm_utils.initialize_llm_provider("anthropic/claude-sonnet-4.6")
    from models import OpenAICompatibleProvider
    assert isinstance(provider, OpenAICompatibleProvider)
