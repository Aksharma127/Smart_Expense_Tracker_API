"""Unit tests for ExpenseService.

All tests use InMemoryExpenseRepository — no disk I/O, no HTTP.
This validates that the service layer's business logic is independently
testable without any infrastructure dependency (plan §8 DIP payoff).

Edge cases explicitly covered (from plan §8):
  - delete non-existent ID → ExpenseNotFoundError, not a silent no-op
  - filter by category with zero matches → empty list, not an error
  - category filter is case-insensitive
  - summary on empty dataset → total=Decimal("0.00"), by_category={}
"""

from datetime import date
from decimal import Decimal

import pytest

from src.core.exceptions import ExpenseNotFoundError
from src.schemas.expense import ExpenseCreate
from src.services.expense_service import ExpenseService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_create_data(
    title: str = "Coffee",
    amount: str = "4.50",
    category: str = "Food",
    expense_date: str = "2024-06-15",
) -> ExpenseCreate:
    return ExpenseCreate(
        title=title,
        amount=Decimal(amount),
        category=category,
        date=date.fromisoformat(expense_date),
    )


# ---------------------------------------------------------------------------
# create_expense
# ---------------------------------------------------------------------------


class TestCreateExpense:
    def test_returns_expense_with_generated_id(self, expense_service: ExpenseService) -> None:
        expense = expense_service.create_expense(make_create_data())
        assert expense.id is not None
        assert len(expense.id) > 0

    def test_id_is_uuid_format(self, expense_service: ExpenseService) -> None:
        import uuid

        expense = expense_service.create_expense(make_create_data())
        # Should not raise
        uuid.UUID(expense.id)

    def test_fields_match_input(self, expense_service: ExpenseService) -> None:
        data = make_create_data(title="Taxi", amount="15.00", category="Transport")
        expense = expense_service.create_expense(data)
        assert expense.title == "Taxi"
        assert expense.amount == Decimal("15.00")
        assert expense.category == "Transport"

    def test_each_expense_gets_unique_id(self, expense_service: ExpenseService) -> None:
        e1 = expense_service.create_expense(make_create_data())
        e2 = expense_service.create_expense(make_create_data())
        assert e1.id != e2.id


# ---------------------------------------------------------------------------
# list_expenses
# ---------------------------------------------------------------------------


class TestListExpenses:
    def test_returns_all_when_no_filter(self, expense_service: ExpenseService) -> None:
        expense_service.create_expense(make_create_data(category="Food"))
        expense_service.create_expense(make_create_data(category="Transport"))
        result = expense_service.list_expenses()
        assert len(result) == 2

    def test_filter_by_category_exact_match(self, expense_service: ExpenseService) -> None:
        expense_service.create_expense(make_create_data(category="Food"))
        expense_service.create_expense(make_create_data(category="Transport"))
        result = expense_service.list_expenses(category="Food")
        assert len(result) == 1
        assert result[0].category == "Food"

    def test_filter_is_case_insensitive(self, expense_service: ExpenseService) -> None:
        """?category=food must match expenses stored as 'Food'."""
        expense_service.create_expense(make_create_data(category="Food"))
        result = expense_service.list_expenses(category="food")
        assert len(result) == 1

    def test_filter_uppercase_case_insensitive(self, expense_service: ExpenseService) -> None:
        expense_service.create_expense(make_create_data(category="Food"))
        result = expense_service.list_expenses(category="FOOD")
        assert len(result) == 1

    def test_filter_zero_matches_returns_empty_list(self, expense_service: ExpenseService) -> None:
        """Zero-match filter must return [] not raise an error."""
        expense_service.create_expense(make_create_data(category="Food"))
        result = expense_service.list_expenses(category="Nonexistent")
        assert result == []

    def test_empty_repo_returns_empty_list(self, expense_service: ExpenseService) -> None:
        assert expense_service.list_expenses() == []


# ---------------------------------------------------------------------------
# get_expense
# ---------------------------------------------------------------------------


class TestGetExpense:
    def test_returns_correct_expense(self, expense_service: ExpenseService) -> None:
        created = expense_service.create_expense(make_create_data(title="Rent"))
        fetched = expense_service.get_expense(created.id)
        assert fetched.id == created.id
        assert fetched.title == "Rent"

    def test_raises_not_found_for_missing_id(self, expense_service: ExpenseService) -> None:
        with pytest.raises(ExpenseNotFoundError) as exc_info:
            expense_service.get_expense("ghost-id")
        assert exc_info.value.expense_id == "ghost-id"


# ---------------------------------------------------------------------------
# delete_expense
# ---------------------------------------------------------------------------


class TestDeleteExpense:
    def test_deletes_existing_expense(self, expense_service: ExpenseService) -> None:
        created = expense_service.create_expense(make_create_data())
        expense_service.delete_expense(created.id)
        assert expense_service.list_expenses() == []

    def test_raises_not_found_for_missing_id(self, expense_service: ExpenseService) -> None:
        """Deleting a non-existent ID must raise ExpenseNotFoundError, not silently pass."""
        with pytest.raises(ExpenseNotFoundError):
            expense_service.delete_expense("does-not-exist")

    def test_only_target_expense_deleted(self, expense_service: ExpenseService) -> None:
        e1 = expense_service.create_expense(make_create_data(title="Keep"))
        e2 = expense_service.create_expense(make_create_data(title="Remove"))
        expense_service.delete_expense(e2.id)
        remaining = expense_service.list_expenses()
        assert len(remaining) == 1
        assert remaining[0].id == e1.id


# ---------------------------------------------------------------------------
# get_summary
# ---------------------------------------------------------------------------


class TestGetSummary:
    def test_empty_dataset_returns_zero_total(self, expense_service: ExpenseService) -> None:
        """Summary on empty dataset must return 0.00 total, not crash."""
        summary = expense_service.get_summary()
        assert summary.total == Decimal("0.00")
        assert summary.count == 0
        assert summary.by_category == {}

    def test_summary_total_correct(self, expense_service: ExpenseService) -> None:
        expense_service.create_expense(make_create_data(amount="10.00"))
        expense_service.create_expense(make_create_data(amount="20.00"))
        summary = expense_service.get_summary()
        assert summary.total == Decimal("30.00")
        assert summary.count == 2

    def test_summary_by_category(self, expense_service: ExpenseService) -> None:
        expense_service.create_expense(make_create_data(amount="10.00", category="Food"))
        expense_service.create_expense(make_create_data(amount="5.00", category="Food"))
        expense_service.create_expense(make_create_data(amount="20.00", category="Transport"))
        summary = expense_service.get_summary()
        assert summary.by_category["Food"] == Decimal("15.00")
        assert summary.by_category["Transport"] == Decimal("20.00")

    def test_summary_decimal_precision(self, expense_service: ExpenseService) -> None:
        """Decimal arithmetic must not introduce float rounding errors."""
        expense_service.create_expense(make_create_data(amount="0.10"))
        expense_service.create_expense(make_create_data(amount="0.20"))
        summary = expense_service.get_summary()
        # 0.1 + 0.2 = 0.3 exactly with Decimal; float would give 0.30000000000000004
        assert summary.total == Decimal("0.30")
