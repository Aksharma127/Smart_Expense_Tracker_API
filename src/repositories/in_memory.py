"""In-memory repository for use in tests.

Satisfies the ExpenseRepository Protocol structurally (no inheritance needed).
Backed by a plain list — no disk I/O, no locking (single-threaded test execution).

Purpose:
  Allows the service layer and integration tests to be exercised without any
  file system involvement, keeping unit tests fast and isolated.
"""

from src.domain.expense import Expense


class InMemoryExpenseRepository:
    """Concrete repository that stores expenses in a Python list.

    Each test gets a fresh instance (via conftest fixtures) so state
    never leaks between test cases.
    """

    def __init__(self) -> None:
        self._store: list[Expense] = []

    def add(self, expense: Expense) -> Expense:
        self._store.append(expense)
        return expense

    def get_all(self) -> list[Expense]:
        return list(self._store)

    def get_by_id(self, expense_id: str) -> Expense | None:
        for expense in self._store:
            if expense.id == expense_id:
                return expense
        return None

    def delete(self, expense_id: str) -> None:
        self._store = [e for e in self._store if e.id != expense_id]
