"""Domain-level exceptions for the expense tracker.

These are pure signal types — no business logic lives here.
They are raised by the service layer and caught by the HTTP layer's
centrally registered exception handlers in main.py.
"""


class ExpenseNotFoundError(Exception):
    """Raised when a requested expense ID does not exist in the repository."""

    def __init__(self, expense_id: str) -> None:
        self.expense_id = expense_id
        super().__init__(f"Expense '{expense_id}' not found")


class InvalidExpenseError(Exception):
    """Raised when a business rule (beyond Pydantic schema validation) is violated."""

    pass
