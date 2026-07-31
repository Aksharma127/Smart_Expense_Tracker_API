"""Integration tests for all HTTP endpoints.

Uses FastAPI's TestClient backed by a temp-file JsonFileExpenseRepository
(wired via dependency_overrides on the get_repository seam in conftest.py).
Each test function gets a fresh, isolated repository — no state leaks.

Covers all 12 scenarios from plan §8:
  - Happy paths for all 6 endpoints
  - 422 on invalid request body
  - 404 on missing ID for GET and DELETE
  - Case-insensitive category filter
  - Zero-match category filter → 200 + []
  - Empty summary → total="0.00", by_category={}
  - Health check
"""

from decimal import Decimal

from fastapi.testclient import TestClient

BASE = "/api/v1/expenses"

VALID_PAYLOAD = {
    "title": "Coffee",
    "amount": "4.50",
    "category": "Food",
    "date": "2024-06-15",
}


# ---------------------------------------------------------------------------
# POST /api/v1/expenses
# ---------------------------------------------------------------------------


class TestCreateExpense:
    def test_create_returns_201(self, test_client: TestClient) -> None:
        response = test_client.post(BASE + "/", json=VALID_PAYLOAD)
        assert response.status_code == 201

    def test_create_response_contains_id(self, test_client: TestClient) -> None:
        response = test_client.post(BASE + "/", json=VALID_PAYLOAD)
        body = response.json()
        assert "id" in body
        assert len(body["id"]) > 0

    def test_create_response_fields_match_input(self, test_client: TestClient) -> None:
        response = test_client.post(BASE + "/", json=VALID_PAYLOAD)
        body = response.json()
        assert body["title"] == "Coffee"
        assert body["amount"] == "4.50"
        assert body["category"] == "Food"
        assert body["date"] == "2024-06-15"

    def test_category_normalised_in_response(self, test_client: TestClient) -> None:
        payload = {**VALID_PAYLOAD, "category": "transport"}
        response = test_client.post(BASE + "/", json=payload)
        assert response.json()["category"] == "Transport"

    def test_negative_amount_returns_422(self, test_client: TestClient) -> None:
        payload = {**VALID_PAYLOAD, "amount": "-5.00"}
        response = test_client.post(BASE + "/", json=payload)
        assert response.status_code == 422

    def test_zero_amount_returns_422(self, test_client: TestClient) -> None:
        payload = {**VALID_PAYLOAD, "amount": "0"}
        response = test_client.post(BASE + "/", json=payload)
        assert response.status_code == 422

    def test_missing_field_returns_422(self, test_client: TestClient) -> None:
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "amount"}
        response = test_client.post(BASE + "/", json=payload)
        assert response.status_code == 422

    def test_invalid_date_returns_422(self, test_client: TestClient) -> None:
        payload = {**VALID_PAYLOAD, "date": "not-a-date"}
        response = test_client.post(BASE + "/", json=payload)
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/expenses
# ---------------------------------------------------------------------------


class TestListExpenses:
    def test_empty_list_returns_200(self, test_client: TestClient) -> None:
        response = test_client.get(BASE + "/")
        assert response.status_code == 200
        assert response.json() == []

    def test_lists_created_expense(self, test_client: TestClient) -> None:
        test_client.post(BASE + "/", json=VALID_PAYLOAD)
        response = test_client.get(BASE + "/")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_category_filter_matches_stored_category(self, test_client: TestClient) -> None:
        test_client.post(BASE + "/", json=VALID_PAYLOAD)
        test_client.post(BASE + "/", json={**VALID_PAYLOAD, "category": "Transport"})
        response = test_client.get(BASE + "/", params={"category": "Food"})
        data = response.json()
        assert response.status_code == 200
        assert len(data) == 1
        assert data[0]["category"] == "Food"

    def test_category_filter_is_case_insensitive(self, test_client: TestClient) -> None:
        """?category=food must match expenses stored with category='Food'."""
        test_client.post(BASE + "/", json=VALID_PAYLOAD)
        response = test_client.get(BASE + "/", params={"category": "food"})
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_category_filter_zero_matches_returns_empty_list(self, test_client: TestClient) -> None:
        """Zero-match filter must return 200 + [] — not 404."""
        test_client.post(BASE + "/", json=VALID_PAYLOAD)
        response = test_client.get(BASE + "/", params={"category": "NonExistent"})
        assert response.status_code == 200
        assert response.json() == []


# ---------------------------------------------------------------------------
# GET /api/v1/expenses/{id}
# ---------------------------------------------------------------------------


class TestGetExpense:
    def test_get_existing_returns_200(self, test_client: TestClient) -> None:
        created = test_client.post(BASE + "/", json=VALID_PAYLOAD).json()
        response = test_client.get(f"{BASE}/{created['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    def test_get_missing_returns_404(self, test_client: TestClient) -> None:
        response = test_client.get(f"{BASE}/does-not-exist")
        assert response.status_code == 404

    def test_404_response_has_uniform_shape(self, test_client: TestClient) -> None:
        """Error responses must have {error, message} shape."""
        response = test_client.get(f"{BASE}/ghost")
        body = response.json()
        assert "error" in body
        assert "message" in body
        assert body["error"] == "not_found"


# ---------------------------------------------------------------------------
# DELETE /api/v1/expenses/{id}
# ---------------------------------------------------------------------------


class TestDeleteExpense:
    def test_delete_existing_returns_204(self, test_client: TestClient) -> None:
        created = test_client.post(BASE + "/", json=VALID_PAYLOAD).json()
        response = test_client.delete(f"{BASE}/{created['id']}")
        assert response.status_code == 204

    def test_delete_removes_expense_from_list(self, test_client: TestClient) -> None:
        created = test_client.post(BASE + "/", json=VALID_PAYLOAD).json()
        test_client.delete(f"{BASE}/{created['id']}")
        listed = test_client.get(BASE + "/").json()
        assert listed == []

    def test_delete_missing_returns_404(self, test_client: TestClient) -> None:
        """Deleting a non-existent ID must return 404 — not a silent no-op."""
        response = test_client.delete(f"{BASE}/does-not-exist")
        assert response.status_code == 404

    def test_delete_204_has_no_body(self, test_client: TestClient) -> None:
        created = test_client.post(BASE + "/", json=VALID_PAYLOAD).json()
        response = test_client.delete(f"{BASE}/{created['id']}")
        assert response.content == b""


# ---------------------------------------------------------------------------
# GET /api/v1/expenses/summary
# ---------------------------------------------------------------------------


class TestGetSummary:
    def test_empty_summary_returns_200(self, test_client: TestClient) -> None:
        response = test_client.get(BASE + "/summary")
        assert response.status_code == 200

    def test_empty_summary_zero_total(self, test_client: TestClient) -> None:
        """Summary on empty dataset must return '0.00' total — not crash."""
        body = test_client.get(BASE + "/summary").json()
        assert body["total"] == "0.00"
        assert body["count"] == 0
        assert body["by_category"] == {}

    def test_summary_with_data_correct_total(self, test_client: TestClient) -> None:
        test_client.post(BASE + "/", json={**VALID_PAYLOAD, "amount": "10.00"})
        test_client.post(BASE + "/", json={**VALID_PAYLOAD, "amount": "20.00"})
        body = test_client.get(BASE + "/summary").json()
        assert Decimal(body["total"]) == Decimal("30.00")
        assert body["count"] == 2

    def test_summary_by_category_breakdown(self, test_client: TestClient) -> None:
        test_client.post(BASE + "/", json={**VALID_PAYLOAD, "amount": "15.00", "category": "Food"})
        test_client.post(
            BASE + "/",
            json={**VALID_PAYLOAD, "amount": "25.00", "category": "Transport"},
        )
        body = test_client.get(BASE + "/summary").json()
        assert Decimal(body["by_category"]["Food"]) == Decimal("15.00")
        assert Decimal(body["by_category"]["Transport"]) == Decimal("25.00")

    def test_summary_route_not_captured_as_id_param(self, test_client: TestClient) -> None:
        """GET /expenses/summary must NOT be mistaken for GET /expenses/{id}.
        If the route order is wrong, this returns 404 instead of 200.
        """
        response = test_client.get(BASE + "/summary")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_returns_200(self, test_client: TestClient) -> None:
        response = test_client.get("/health")
        assert response.status_code == 200

    def test_health_response_shape(self, test_client: TestClient) -> None:
        body = test_client.get("/health").json()
        assert body["status"] == "ok"
