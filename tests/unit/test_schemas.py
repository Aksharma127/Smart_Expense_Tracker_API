"""Unit tests for Pydantic V2 schemas.

Tests operate directly on schema instantiation — no HTTP, no service, no disk.
Validates that all field constraints and validators fire correctly.
"""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.schemas.expense import ExpenseCreate, ExpenseRead, SummaryResponse

# ---------------------------------------------------------------------------
# Valid baseline
# ---------------------------------------------------------------------------

VALID_PAYLOAD = {
    "title": "Lunch",
    "amount": Decimal("12.50"),
    "category": "food",
    "date": date(2024, 6, 15),
}


class TestExpenseCreateAmount:
    def test_valid_amount_accepted(self) -> None:
        schema = ExpenseCreate(**VALID_PAYLOAD)
        assert schema.amount == Decimal("12.50")

    def test_zero_amount_rejected(self) -> None:
        with pytest.raises(ValidationError, match="greater than 0"):
            ExpenseCreate(**{**VALID_PAYLOAD, "amount": Decimal("0")})

    def test_negative_amount_rejected(self) -> None:
        with pytest.raises(ValidationError, match="greater than 0"):
            ExpenseCreate(**{**VALID_PAYLOAD, "amount": Decimal("-5.00")})

    def test_amount_too_many_decimal_places_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExpenseCreate(**{**VALID_PAYLOAD, "amount": Decimal("1.999")})

    def test_amount_is_decimal_type(self) -> None:
        schema = ExpenseCreate(**VALID_PAYLOAD)
        assert isinstance(schema.amount, Decimal)

    def test_amount_string_input_coerced_correctly(self) -> None:
        """Pydantic V2 coerces string "12.50" to Decimal("12.50")."""
        schema = ExpenseCreate(**{**VALID_PAYLOAD, "amount": "12.50"})
        assert schema.amount == Decimal("12.50")


class TestExpenseCreateTitle:
    def test_valid_title_accepted(self) -> None:
        schema = ExpenseCreate(**VALID_PAYLOAD)
        assert schema.title == "Lunch"

    def test_empty_string_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExpenseCreate(**{**VALID_PAYLOAD, "title": ""})

    def test_whitespace_only_rejected(self) -> None:
        """Title that is blank after stripping must be rejected."""
        with pytest.raises(ValidationError, match="blank"):
            ExpenseCreate(**{**VALID_PAYLOAD, "title": "   "})

    def test_title_is_stripped(self) -> None:
        schema = ExpenseCreate(**{**VALID_PAYLOAD, "title": "  Coffee  "})
        assert schema.title == "Coffee"

    def test_title_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExpenseCreate(**{**VALID_PAYLOAD, "title": "x" * 201})


class TestExpenseCreateCategory:
    def test_category_normalised_to_title_case(self) -> None:
        schema = ExpenseCreate(**{**VALID_PAYLOAD, "category": "food"})
        assert schema.category == "Food"

    def test_category_uppercase_normalised(self) -> None:
        schema = ExpenseCreate(**{**VALID_PAYLOAD, "category": "TRANSPORT"})
        assert schema.category == "Transport"

    def test_category_stripped(self) -> None:
        schema = ExpenseCreate(**{**VALID_PAYLOAD, "category": "  utilities  "})
        assert schema.category == "Utilities"

    def test_empty_category_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExpenseCreate(**{**VALID_PAYLOAD, "category": ""})

    def test_category_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExpenseCreate(**{**VALID_PAYLOAD, "category": "x" * 51})


class TestExpenseCreateDate:
    def test_valid_date_accepted(self) -> None:
        schema = ExpenseCreate(**VALID_PAYLOAD)
        assert schema.date == date(2024, 6, 15)

    def test_invalid_date_string_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ExpenseCreate(**{**VALID_PAYLOAD, "date": "not-a-date"})

    def test_missing_date_rejected(self) -> None:
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "date"}
        with pytest.raises(ValidationError):
            ExpenseCreate(**payload)


class TestExpenseRead:
    def test_expense_read_requires_id(self) -> None:
        with pytest.raises(ValidationError):
            ExpenseRead(**VALID_PAYLOAD)  # missing id

    def test_expense_read_accepts_id(self) -> None:
        schema = ExpenseRead(**VALID_PAYLOAD, id="some-uuid")
        assert schema.id == "some-uuid"


class TestSummaryResponse:
    def test_valid_summary(self) -> None:
        s = SummaryResponse(
            total=Decimal("100.00"),
            count=2,
            by_category={"Food": Decimal("60.00"), "Transport": Decimal("40.00")},
        )
        assert s.total == Decimal("100.00")
        assert s.count == 2
        assert len(s.by_category) == 2

    def test_empty_summary(self) -> None:
        s = SummaryResponse(total=Decimal("0.00"), count=0, by_category={})
        assert s.total == Decimal("0.00")
        assert s.by_category == {}
