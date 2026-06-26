def test_job_crud_flow(client):
    # create
    created = client.post("/jobs", json={"label": "Backend", "description": "JD text"})
    assert created.status_code == 200
    job = created.json()
    assert job["id"] >= 1
    assert job["included"] is True

    # list
    assert len(client.get("/jobs").json()) == 1

    # toggle included off + edit label
    patched = client.patch(f"/jobs/{job['id']}",
                           json={"included": False, "label": "Backend (paused)"})
    assert patched.status_code == 200
    assert patched.json()["included"] is False
    assert patched.json()["label"] == "Backend (paused)"

    # delete
    assert client.delete(f"/jobs/{job['id']}").status_code == 200
    assert client.get("/jobs").json() == []


def test_patch_missing_job_returns_404(client):
    assert client.patch("/jobs/999", json={"included": False}).status_code == 404
