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


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A TestClient backed by a fresh temp SQLite DB, with startup side effects
    neutralized so tests touch no real DB file or uploads dir."""
    from sqlmodel import SQLModel, create_engine, Session
    from fastapi.testclient import TestClient
    import db
    import db_models  # noqa: F401  (registers tables)
    import api

    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(test_engine)

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    monkeypatch.setattr(api, "init_db", lambda: None)
    monkeypatch.setattr(api, "UPLOAD_DIR", tmp_path / "uploads")
    api.app.dependency_overrides[db.get_session] = override_get_session

    with TestClient(api.app) as test_client:
        yield test_client

    api.app.dependency_overrides.clear()
