"""Router-level tests for GET /insights and GET /insights/salary.

Uses FastAPI TestClient with the in-memory SQLite session override from conftest.
The insights service is mocked so no network calls are made.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

# conftest.py at tests/ provides `client` and `session` fixtures.


_MOCK_INSIGHTS = {
    "region": "in",
    "currency": "INR",
    "generated_at": datetime.now(UTC).isoformat(),
    "news": [
        {
            "title": "AI hiring surge",
            "url": "https://example.com",
            "domain": "example.com",
            "seendate": "20260614T100000Z",
        }
    ],
    "salaries": [
        {"role": "Software Engineer", "median": 1200000.0, "currency": "INR", "sample_size": 500}
    ],
    "hottest_fields": [
        {
            "label": "IT Jobs",
            "tag": "it-jobs",
            "openings": 12500,
            "mean_salary": 900000.0,
            "currency": "INR",
        }
    ],
    "trends": {
        "salary_history": [{"period": "2024-01", "value": 1100000.0}],
        "unemployment": [{"year": 2023, "value": 7.1}],
        "employment": [{"year": 2023, "value": 45.2}],
    },
}

_MOCK_SALARY = {
    "role": "Data Scientist",
    "median": 1500000.0,
    "currency": "INR",
    "sample_size": 300,
}


# ---------------------------------------------------------------------------
# GET /insights?region=in — happy path
# ---------------------------------------------------------------------------


def test_get_insights_happy_path(client: TestClient):
    with patch(
        "backend.routers.insights.get_insights",
        new=AsyncMock(return_value=_MOCK_INSIGHTS),
    ):
        response = client.get("/insights?region=in")

    assert response.status_code == 200
    data = response.json()
    assert data["region"] == "in"
    assert data["currency"] == "INR"
    assert "generated_at" in data
    assert isinstance(data["news"], list)
    assert isinstance(data["salaries"], list)
    assert isinstance(data["hottest_fields"], list)
    assert "trends" in data


def test_get_insights_response_has_all_required_keys(client: TestClient):
    with patch(
        "backend.routers.insights.get_insights",
        new=AsyncMock(return_value=_MOCK_INSIGHTS),
    ):
        response = client.get("/insights?region=in")

    assert response.status_code == 200
    data = response.json()
    required = {
        "region",
        "currency",
        "generated_at",
        "news",
        "salaries",
        "hottest_fields",
        "trends",
    }
    assert required.issubset(data.keys())


def test_get_insights_news_items_have_correct_shape(client: TestClient):
    with patch(
        "backend.routers.insights.get_insights",
        new=AsyncMock(return_value=_MOCK_INSIGHTS),
    ):
        response = client.get("/insights?region=in")

    news = response.json()["news"]
    assert len(news) == 1
    item = news[0]
    assert set(item.keys()) >= {"title", "url", "domain", "seendate"}


def test_get_insights_salary_rows_have_correct_shape(client: TestClient):
    with patch(
        "backend.routers.insights.get_insights",
        new=AsyncMock(return_value=_MOCK_INSIGHTS),
    ):
        response = client.get("/insights?region=in")

    salaries = response.json()["salaries"]
    assert len(salaries) == 1
    row = salaries[0]
    assert set(row.keys()) >= {"role", "median", "currency", "sample_size"}


# ---------------------------------------------------------------------------
# GET /insights?region=xx — unknown region → 400
# ---------------------------------------------------------------------------


def test_get_insights_unknown_region_returns_400(client: TestClient):
    with patch(
        "backend.routers.insights.get_insights",
        new=AsyncMock(side_effect=ValueError("Unknown region code: 'xx'")),
    ):
        response = client.get("/insights?region=xx")

    assert response.status_code == 400
    assert "detail" in response.json()


def test_get_insights_default_region_is_in(client: TestClient):
    """When region param is omitted, default 'in' should be used without error."""
    with patch(
        "backend.routers.insights.get_insights",
        new=AsyncMock(return_value=_MOCK_INSIGHTS),
    ):
        response = client.get("/insights")

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /insights/salary?role=...&region=us — happy path
# ---------------------------------------------------------------------------


def test_get_salary_happy_path(client: TestClient):
    with patch(
        "backend.routers.insights.get_salary",
        new=AsyncMock(return_value=_MOCK_SALARY),
    ):
        response = client.get("/insights/salary?role=Data+Scientist&region=in")

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "Data Scientist"
    assert data["median"] == pytest.approx(1500000.0)
    assert data["currency"] == "INR"
    assert data["sample_size"] == 300


def test_get_salary_null_median(client: TestClient):
    """A null median must be serialised as null (not omitted or zero)."""
    with patch(
        "backend.routers.insights.get_salary",
        new=AsyncMock(
            return_value={"role": "Rare Role", "median": None, "currency": "USD", "sample_size": 0}
        ),
    ):
        response = client.get("/insights/salary?role=Rare+Role&region=us")

    assert response.status_code == 200
    assert response.json()["median"] is None


def test_get_salary_unknown_region_returns_400(client: TestClient):
    with patch(
        "backend.routers.insights.get_salary",
        new=AsyncMock(side_effect=ValueError("Unknown region code: 'zz'")),
    ):
        response = client.get("/insights/salary?role=Engineer&region=zz")

    assert response.status_code == 400


def test_get_salary_missing_role_returns_422(client: TestClient):
    """role param is required; missing it should return 422 Unprocessable Entity."""
    response = client.get("/insights/salary?region=us")
    assert response.status_code == 422


def test_get_salary_empty_role_returns_422(client: TestClient):
    """role param must be at least 1 character (min_length=1)."""
    response = client.get("/insights/salary?role=&region=us")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Valid region codes — spot-check each
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("region", ["in", "us", "gb", "world"])
def test_get_insights_all_valid_regions_return_200(client: TestClient, region: str):
    mock_data = {**_MOCK_INSIGHTS, "region": region}
    with patch(
        "backend.routers.insights.get_insights",
        new=AsyncMock(return_value=mock_data),
    ):
        response = client.get(f"/insights?region={region}")

    assert response.status_code == 200
    assert response.json()["region"] == region
