import io
import service


def test_upload_resume_persists_and_returns_id(client, monkeypatch):
    class _FakeResumeObj:
        def model_dump_json(self):
            return '{"basics": {"name": "Test"}}'

    monkeypatch.setattr(service, "load_resume", lambda p: _FakeResumeObj())
    monkeypatch.setattr(service, "resume_to_text", lambda r: "RESUME TEXT")
    monkeypatch.setattr(service, "github_to_text", lambda r: "GH TEXT")

    resp = client.post(
        "/resumes",
        files={"file": ("cv.pdf", io.BytesIO(b"%PDF-fake"), "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] >= 1
    assert body["filename"] == "cv.pdf"

    listed = client.get("/resumes").json()
    assert len(listed) == 1
    assert listed[0]["filename"] == "cv.pdf"

    detail = client.get(f"/resumes/{body['id']}").json()
    assert detail["parsed"]["basics"]["name"] == "Test"


def test_upload_unparseable_pdf_returns_422(client, monkeypatch):
    monkeypatch.setattr(service, "load_resume", lambda p: None)
    resp = client.post(
        "/resumes",
        files={"file": ("bad.pdf", io.BytesIO(b"x"), "application/pdf")},
    )
    assert resp.status_code == 422


def test_get_missing_resume_returns_404(client):
    assert client.get("/resumes/999").status_code == 404
