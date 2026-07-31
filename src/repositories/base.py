"""Abstract repository interface using typing.Protocol (structural subtyping).

Why Protocol over ABC:
  Concrete repository classes do not need to import or inherit from this base.
  They are interchangeable as long as they structurally match the interface —
  this satisfies OCP and LSP without coupling the implementations to this module.

Interface contract: exactly 4 methods, nothing more (ISP — plan §2).
"""

from typing import Protocol

from src.domain.expense import Expense


class ExpenseRepository(Protocol):
    """Defines the persistence contract for Expense entities.

    Any class that implements these four methods satisfies this Protocol,
    whether it's JsonFileExpenseRepository or InMemoryExpenseRepository.
    """

    def add(self, expense: Expense) -> Expense:
        """Persist a new expense and return it."""
        ...

    def get_all(self) -> list[Expense]:
        """Return every stored expense."""
        ...

    def get_by_id(self, expense_id: str) -> Expense | None:
        """Return the expense with the given ID, or None if not found."""
        ...

    def delete(self, expense_id: str) -> None:
        """Remove the expense with the given ID.

        Does NOT raise if the ID is absent — that responsibility belongs
        to the service layer, which decides what a missing delete means.
        """
        ...
