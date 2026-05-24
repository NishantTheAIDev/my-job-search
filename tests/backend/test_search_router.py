import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.models.search_job import SearchJobStatus


def test_create_search_returns_job_id(client: TestClient):
    with patch("backend.routers.search.start_search_task"):
        response = client.post("/search", json={"query": "software engineer"})
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"


def test_get_search_status_not_found(client: TestClient):
    random_id = str(uuid.uuid4())
    response = client.get(f"/search/{random_id}/status")
    assert response.status_code == 404


def test_get_search_status_after_create(client: TestClient):
    with patch("backend.routers.search.start_search_task"):
        create_response = client.post("/search", json={"query": "data engineer"})
    assert create_response.status_code == 200
    job_id = create_response.json()["job_id"]

    status_response = client.get(f"/search/{job_id}/status")
    assert status_response.status_code == 200
    data = status_response.json()
    assert data["job_id"] == job_id
    assert data["status"] in [s.value for s in SearchJobStatus]


def test_list_jobs_empty(client: TestClient):
    search_job_id = str(uuid.uuid4())
    response = client.get(f"/jobs?search_job_id={search_job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_get_job_not_found(client: TestClient):
    random_id = str(uuid.uuid4())
    response = client.get(f"/jobs/{random_id}")
    assert response.status_code == 404
