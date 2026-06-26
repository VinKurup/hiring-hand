import ingest


def test_github_to_text_no_profile_returns_header_only():
    class FakeBasics:
        profiles = []

    class FakeResume:
        basics = FakeBasics()

    text = ingest.github_to_text(FakeResume())
    assert "GITHUB DATA" in text  # upstream converter emits the header for {}


def test_github_to_text_handles_none_resume():
    text = ingest.github_to_text(None)
    assert "GITHUB DATA" in text


def test_run_pipeline_reexports_adapters():
    import run_pipeline
    assert run_pipeline._load_resume is ingest.load_resume
    assert run_pipeline._load_resume_text is ingest.resume_to_text
    assert run_pipeline._load_github_text is ingest.github_to_text
