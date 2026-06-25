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
