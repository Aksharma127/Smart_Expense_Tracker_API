"""Unit tests for JsonFileExpenseRepository.

Tests are isolated to the repository layer only — no service, no HTTP.
All disk I/O uses pytest's `tmp_path` fixture; the real data/ directory
is never accessed.

Coverage targets (from plan §8):
  - Data persists across a second repository instance on the same path
  - Bootstrap: creates the JSON file as [] if it doesn't exist
  - add / get_all / get_by_id / delete behave correctly
  - Atomic write: .tmp file is cleaned up after a successful write
  - Decimal and date types survive a full serialise → file → deserialise round-trip
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

from src.domain.expense import Expense
from src.repositories.json_file import JsonFileExpenseRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_expense(
    id_: str = "uuid-001",
    title: str = "Coffee",
    amount: str = "4.50",
    category: str = "Food",
    expense_date: str = "2024-06-15",
) -> Expense:
    """Factory for Expense domain objects used in tests."""
    return Expense(
        id=id_,
        title=title,
        amount=Decimal(amount),
        category=category,
        date=date.fromisoformat(expense_date),
    )


# ---------------------------------------------------------------------------
# Bootstrap tests
# ---------------------------------------------------------------------------


class TestBootstrap:
    def test_creates_file_when_missing(self, tmp_json_path: Path) -> None:
        """Repository must create an empty expenses.json if the path doesn't exist."""
        assert not tmp_json_path.exists()
        JsonFileExpenseRepository(tmp_json_path)
        assert tmp_json_path.exists()

    def test_bootstrap_file_is_valid_empty_array(self, tmp_json_path: Path) -> None:
        """The bootstrapped file must contain [] so get_all() returns an empty list."""
        repo = JsonFileExpenseRepository(tmp_json_path)
        assert repo.get_all() == []

    def test_does_not_overwrite_existing_file(self, tmp_json_path: Path) -> None:
        """Opening an existing, non-empty file must not reset it."""
        repo1 = JsonFileExpenseRepository(tmp_json_path)
        expense = make_expense()
        repo1.add(expense)

        repo2 = JsonFileExpenseRepository(tmp_json_path)
        assert len(repo2.get_all()) == 1


# ---------------------------------------------------------------------------
# Persistence across instances
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_add_persists_to_disk(self, tmp_json_path: Path) -> None:
        """Data written by one repository instance must be readable by a new one."""
        repo1 = JsonFileExpenseRepository(tmp_json_path)
        expense = make_expense()
        repo1.add(expense)

        # Simulate process restart: new instance on the same path.
        repo2 = JsonFileExpenseRepository(tmp_json_path)
        loaded = repo2.get_all()

        assert len(loaded) == 1
        assert loaded[0].id == expense.id
        assert loaded[0].title == expense.title
        assert loaded[0].amount == expense.amount
        assert loaded[0].category == expense.category
        assert loaded[0].date == expense.date

    def test_decimal_survives_round_trip(self, tmp_json_path: Path) -> None:
        """Decimal precision must not degrade through JSON serialisation."""
        repo1 = JsonFileExpenseRepository(tmp_json_path)
        expense = make_expense(amount="99.99")
        repo1.add(expense)

        repo2 = JsonFileExpenseRepository(tmp_json_path)
        loaded = repo2.get_all()[0]

        assert loaded.amount == Decimal("99.99")
        assert isinstance(loaded.amount, Decimal)

    def test_date_survives_round_trip(self, tmp_json_path: Path) -> None:
        """date objects must deserialise back to date, not strings."""
        repo1 = JsonFileExpenseRepository(tmp_json_path)
        expense = make_expense(expense_date="2024-12-31")
        repo1.add(expense)

        repo2 = JsonFileExpenseRepository(tmp_json_path)
        loaded = repo2.get_all()[0]

        assert loaded.date == date(2024, 12, 31)
        assert isinstance(loaded.date, date)

    def test_multiple_expenses_persist(self, tmp_json_path: Path) -> None:
        """All added expenses must survive a round-trip, preserving order."""
        repo1 = JsonFileExpenseRepository(tmp_json_path)
        e1 = make_expense(id_="id-1", title="Lunch")
        e2 = make_expense(id_="id-2", title="Taxi")
        repo1.add(e1)
        repo1.add(e2)

        repo2 = JsonFileExpenseRepository(tmp_json_path)
        loaded = repo2.get_all()

        assert len(loaded) == 2
        assert loaded[0].id == "id-1"
        assert loaded[1].id == "id-2"


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


class TestCRUD:
    def test_add_returns_the_expense(self, tmp_json_path: Path) -> None:
        """add() must return the same Expense object it received."""
        repo = JsonFileExpenseRepository(tmp_json_path)
        expense = make_expense()
        result = repo.add(expense)
        assert result is expense

    def test_get_all_returns_empty_list_initially(self, tmp_json_path: Path) -> None:
        repo = JsonFileExpenseRepository(tmp_json_path)
        assert repo.get_all() == []

    def test_get_by_id_returns_correct_expense(self, tmp_json_path: Path) -> None:
        repo = JsonFileExpenseRepository(tmp_json_path)
        e1 = make_expense(id_="aaa", title="Rent")
        e2 = make_expense(id_="bbb", title="Coffee")
        repo.add(e1)
        repo.add(e2)

        result = repo.get_by_id("aaa")
        assert result is not None
        assert result.id == "aaa"
        assert result.title == "Rent"

    def test_get_by_id_returns_none_when_missing(self, tmp_json_path: Path) -> None:
        repo = JsonFileExpenseRepository(tmp_json_path)
        assert repo.get_by_id("nonexistent") is None

    def test_delete_removes_correct_expense(self, tmp_json_path: Path) -> None:
        repo = JsonFileExpenseRepository(tmp_json_path)
        e1 = make_expense(id_="del-me", title="Old expense")
        e2 = make_expense(id_="keep-me", title="Keeper")
        repo.add(e1)
        repo.add(e2)

        repo.delete("del-me")

        remaining = repo.get_all()
        assert len(remaining) == 1
        assert remaining[0].id == "keep-me"

    def test_delete_nonexistent_is_silent(self, tmp_json_path: Path) -> None:
        """Repository.delete() does not raise on a missing ID.
        The 404 enforcement responsibility belongs to the service layer.
        """
        repo = JsonFileExpenseRepository(tmp_json_path)
        # Should not raise
        repo.delete("ghost-id")

    def test_delete_persists_to_disk(self, tmp_json_path: Path) -> None:
        """After delete(), a new repository instance must not see the deleted expense."""
        repo1 = JsonFileExpenseRepository(tmp_json_path)
        expense = make_expense(id_="gone")
        repo1.add(expense)
        repo1.delete("gone")

        repo2 = JsonFileExpenseRepository(tmp_json_path)
        assert repo2.get_by_id("gone") is None
        assert repo2.get_all() == []


# ---------------------------------------------------------------------------
# Atomic write verification
# ---------------------------------------------------------------------------


class TestAtomicWrite:
    def test_tmp_file_is_cleaned_up_after_write(self, tmp_json_path: Path) -> None:
        """After a successful write, the .tmp sibling file must not exist."""
        repo = JsonFileExpenseRepository(tmp_json_path)
        repo.add(make_expense())

        tmp_file = tmp_json_path.with_suffix(".tmp")
        assert not tmp_file.exists(), "Atomic write left a .tmp file behind after a successful write"

    def test_json_file_is_valid_after_write(self, tmp_json_path: Path) -> None:
        """The written JSON file must be parseable after add()."""
        import json

        repo = JsonFileExpenseRepository(tmp_json_path)
        repo.add(make_expense(amount="12.99"))

        content = tmp_json_path.read_text(encoding="utf-8")
        parsed = json.loads(content)

        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["amount"] == "12.99"
