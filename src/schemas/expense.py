"""Pydantic V2 request/response schemas (DTOs).

Design decisions:
  - ExpenseCreate (input, no id) and ExpenseRead (output, with id) are
    kept as separate models. This is intentional: the server owns identity,
    and mixing input/output contracts into a single model is an API smell.
  - amount uses Decimal with decimal_places=2 and max_digits=12. Using float
    would introduce 0.1+0.2 != 0.3 rounding errors in summary totals.
  - category is a plain str (not an Enum). The assignment defines no fixed
    category set; an Enum would silently reject valid user categories.
  - category is normalised to title-case so "food" and "Food" don't produce
    two separate buckets in summary breakdowns.
"""

from datetime import date as date_type
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExpenseCreate(BaseModel):
    """Request body for POST /expenses. No `id` — the server generates it."""

    title: str = Field(..., min_length=1, max_length=200, description="Expense description")
    amount: Decimal = Field(
        ...,
        gt=0,
        decimal_places=2,
        max_digits=12,
        description="Monetary amount (positive, max 2 decimal places)",
    )
    category: str = Field(..., min_length=1, max_length=50, description="Expense category")
    date: date_type = Field(..., description="Date of the expense (YYYY-MM-DD)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Coffee",
                "amount": "4.50",
                "category": "Food",
                "date": "2024-06-15",
            }
        }
    )

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("title must not be blank after stripping whitespace")
        return stripped

    @field_validator("category")
    @classmethod
    def normalize_category(cls, v: str) -> str:
        normalised = v.strip().title()
        if not normalised:
            raise ValueError("category must not be blank after stripping whitespace")
        return normalised


class ExpenseRead(ExpenseCreate):
    """Response body. Extends ExpenseCreate with the server-generated id."""

    id: str = Field(..., description="Server-generated UUID for the expense")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "title": "Coffee",
                "amount": "4.50",
                "category": "Food",
                "date": "2024-06-15",
            }
        }
    )


class SummaryResponse(BaseModel):
    """Response body for GET /expenses/summary."""

    total: Decimal = Field(..., description="Sum of all expense amounts")
    count: int = Field(..., description="Total number of expenses")
    by_category: dict[str, Decimal] = Field(..., description="Total amount grouped by category")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": "482.50",
                "count": 7,
                "by_category": {
                    "Food": "210.00",
                    "Transport": "150.50",
                    "Utilities": "122.00",
                },
            }
        }
    )
