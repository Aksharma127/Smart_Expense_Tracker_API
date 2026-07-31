"""Expense CRUD and summary HTTP endpoints.

Route registration order is intentional and critical:
  /summary MUST be registered before /{expense_id}.
  FastAPI matches routes in registration order. If /{expense_id} came first,
  a request to GET /expenses/summary would have "summary" captured as an ID
  path parameter and route to get_expense(), not get_summary().

All handlers convert Expense domain objects to ExpenseRead response models
using the private _to_read() helper — the domain layer has no Pydantic dep.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from src.api.deps import get_service
from src.domain.expense import Expense
from src.schemas.expense import ExpenseCreate, ExpenseRead, SummaryResponse
from src.services.expense_service import ExpenseService

router = APIRouter(prefix="/api/v1/expenses", tags=["Expenses"], redirect_slashes=False)


def _to_read(expense: Expense) -> ExpenseRead:
    """Convert a domain Expense to an ExpenseRead response model."""
    return ExpenseRead(
        id=expense.id,
        title=expense.title,
        amount=expense.amount,
        category=expense.category,
        date=expense.date,
    )


@router.post(
    "",
    response_model=ExpenseRead,
    status_code=201,
    summary="Create a new expense",
    description="Persists a new expense. The server generates the `id`; do not include it in the request body.",
)
def create_expense(
    data: ExpenseCreate,
    service: Annotated[ExpenseService, Depends(get_service)],
) -> ExpenseRead:
    expense = service.create_expense(data)
    return _to_read(expense)


# /summary MUST come before /{expense_id} — see module docstring.
@router.get(
    "/summary",
    response_model=SummaryResponse,
    summary="Get expense summary",
    description=(
        "Returns the overall total and a breakdown of totals by category. "
        "Returns `total: '0.00'` on an empty dataset."
    ),
)
def get_summary(
    service: Annotated[ExpenseService, Depends(get_service)],
) -> SummaryResponse:
    return service.get_summary()


@router.get(
    "",
    response_model=list[ExpenseRead],
    summary="List all expenses",
    description=(
        "Returns all expenses. Use `?category=<name>` to filter (case-insensitive). "
        "Returns an empty list — not 404 — when the filter matches nothing."
    ),
)
def list_expenses(
    service: Annotated[ExpenseService, Depends(get_service)],
    category: str | None = Query(
        None,
        description="Filter by category name (case-insensitive). Omit to return all.",
    ),
) -> list[ExpenseRead]:
    return [_to_read(e) for e in service.list_expenses(category)]


@router.get(
    "/{expense_id}",
    response_model=ExpenseRead,
    summary="Get an expense by ID",
    description="Returns a single expense. Returns 404 if the ID does not exist.",
)
def get_expense(
    expense_id: str,
    service: Annotated[ExpenseService, Depends(get_service)],
) -> ExpenseRead:
    return _to_read(service.get_expense(expense_id))


@router.delete(
    "/{expense_id}",
    status_code=204,
    summary="Delete an expense",
    description="Deletes a single expense. Returns 404 if the ID does not exist. Returns 204 with no body on success.",
)
def delete_expense(
    expense_id: str,
    service: Annotated[ExpenseService, Depends(get_service)],
) -> Response:
    service.delete_expense(expense_id)
    return Response(status_code=204)
