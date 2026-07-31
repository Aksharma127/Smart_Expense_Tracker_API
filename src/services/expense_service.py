"""Business logic layer for expense management.

Architectural rules enforced here:
  - Depends on ExpenseRepository (Protocol), never the concrete class (DIP).
  - Has zero knowledge of HTTP, JSON, or FastAPI.
  - UUID generation happens here, never accepted from clients.
  - delete() is NOT a silent no-op — raises ExpenseNotFoundError if missing.
  - get_summary() returns Decimal("0.00") total and empty dict on an empty
    dataset, never crashes.
"""

import uuid
from decimal import Decimal

from src.core.exceptions import ExpenseNotFoundError
from src.domain.expense import Expense
from src.repositories.base import ExpenseRepository
from src.schemas.expense import ExpenseCreate, SummaryResponse


class ExpenseService:
    """Orchestrates all expense business operations.

    Injected with an ExpenseRepository at construction time (DIP).
    FastAPI's dependency injection wires the concrete class at runtime;
    tests inject InMemoryExpenseRepository directly.
    """

    def __init__(self, repo: ExpenseRepository) -> None:
        self._repo = repo

    def create_expense(self, data: ExpenseCreate) -> Expense:
        """Create a new expense with a server-generated UUID."""
        expense = Expense(
            id=str(uuid.uuid4()),
            title=data.title,
            amount=data.amount,
            category=data.category,
            date=data.date,
        )
        return self._repo.add(expense)

    def list_expenses(self, category: str | None = None) -> list[Expense]:
        """Return all expenses, optionally filtered by category (case-insensitive).

        Returns an empty list (not a 404) when the filter matches nothing.
        """
        all_expenses = self._repo.get_all()
        if category is None:
            return all_expenses
        return [e for e in all_expenses if e.category.lower() == category.lower()]

    def get_expense(self, expense_id: str) -> Expense:
        """Fetch a single expense by ID. Raises ExpenseNotFoundError if absent."""
        expense = self._repo.get_by_id(expense_id)
        if expense is None:
            raise ExpenseNotFoundError(expense_id)
        return expense

    def delete_expense(self, expense_id: str) -> None:
        """Delete an expense by ID. Raises ExpenseNotFoundError if absent.

        This is NOT a silent no-op — deleting a non-existent ID is an error
        that the caller (HTTP layer) should surface as a 404.
        """
        self.get_expense(expense_id)
        self._repo.delete(expense_id)

    def get_summary(self) -> SummaryResponse:
        """Compute overall total and per-category totals using Decimal arithmetic.

        Returns total="0.00" and by_category={} on an empty dataset — no crash.
        All arithmetic uses Decimal to avoid float rounding errors in totals.
        """
        expenses = self._repo.get_all()
        total = Decimal("0.00")
        by_category: dict[str, Decimal] = {}

        for expense in expenses:
            total += expense.amount
            by_category[expense.category] = by_category.get(expense.category, Decimal("0.00")) + expense.amount

        return SummaryResponse(total=total, count=len(expenses), by_category=by_category)
