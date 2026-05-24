import io

from fastapi.testclient import TestClient


def test_get_resume_no_resume(client: TestClient):
    response = client.get("/resume")
    assert response.status_code == 404


def test_upload_txt_resume(client: TestClient):
    content = b"John Doe\nSoftware Engineer\n5 years Python experience"
    response = client.post(
        "/resume/upload",
        files={"file": ("resume.txt", io.BytesIO(content), "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "resume.txt"
    assert "John Doe" in data["text_preview"]


def test_get_resume_after_upload(client: TestClient):
    content = b"Jane Smith\nData Engineer"
    client.post(
        "/resume/upload",
        files={"file": ("my_resume.txt", io.BytesIO(content), "text/plain")},
    )
    response = client.get("/resume")
    assert response.status_code == 200
    assert response.json()["filename"] == "my_resume.txt"


def test_second_upload_deactivates_first(client: TestClient):
    client.post(
        "/resume/upload",
        files={"file": ("first.txt", io.BytesIO(b"First resume"), "text/plain")},
    )
    client.post(
        "/resume/upload",
        files={"file": ("second.txt", io.BytesIO(b"Second resume"), "text/plain")},
    )
    response = client.get("/resume")
    assert response.status_code == 200
    assert response.json()["filename"] == "second.txt"
