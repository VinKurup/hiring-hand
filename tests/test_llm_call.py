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
