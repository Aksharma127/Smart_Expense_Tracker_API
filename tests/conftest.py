"""Shared pytest fixtures used across unit and integration test suites.

Isolation guarantee:
  - All fixtures are function-scoped (default), so each test gets a fresh
    instance — no state leaks between tests.
  - `tmp_json_path` uses pytest's `tmp_path` fixture (unique dir per test).
  - `test_client` overrides `get_repository` so integration tests never
    touch the real data/expenses.json file.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.domain.expense import Expense
from src.repositories.in_memory import InMemoryExpenseRepository
from src.repositories.json_file import JsonFileExpenseRepository
from src.services.expense_service import ExpenseService

# ---------------------------------------------------------------------------
# Repository fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def in_memory_repo() -> InMemoryExpenseRepository:
    """Fresh InMemoryExpenseRepository per test function."""
    return InMemoryExpenseRepository()


@pytest.fixture
def tmp_json_path(tmp_path: Path) -> Path:
    """A temporary path for a JSON file — unique per test, never touches data/."""
    return tmp_path / "test_expenses.json"


# ---------------------------------------------------------------------------
# Service fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def expense_service(in_memory_repo: InMemoryExpenseRepository) -> ExpenseService:
    """ExpenseService wired to a fresh InMemoryExpenseRepository."""
    return ExpenseService(in_memory_repo)


# ---------------------------------------------------------------------------
# Integration test client
# ---------------------------------------------------------------------------


@pytest.fixture
def test_client(tmp_json_path: Path) -> TestClient:  # type: ignore[return]
    """TestClient with get_repository overridden to use a temp JSON file.

    This ensures integration tests are fully isolated from the real
    data/expenses.json file, and each test starts with an empty dataset.
    """
    from src.api.deps import get_repository
    from src.main import app

    def override_get_repository() -> JsonFileExpenseRepository:
        return JsonFileExpenseRepository(tmp_json_path)

    app.dependency_overrides[get_repository] = override_get_repository
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Domain object factory
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_expense() -> Expense:
    """A valid Expense domain object for use as test data."""
    return Expense(
        id="test-uuid-1234",
        title="Coffee",
        amount=Decimal("4.50"),
        category="Food",
        date=date(2024, 6, 15),
    )
