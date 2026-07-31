"""JSON file-backed repository for Expense persistence.

Two production-grade details distinguish this from a naive file write:

1. Atomic write (plan §7):
   All writes go to a .tmp file first, then os.replace() renames it into
   place. os.replace() is atomic on POSIX (rename(2) syscall). If the
   process dies mid-write, the .tmp file is left orphaned — the real
   expenses.json is never corrupted.

2. Thread lock (plan §7):
   FastAPI runs synchronous path functions in a thread pool executor.
   Without a lock, two concurrent requests performing read-modify-write
   cycles can interleave and silently drop each other's writes. A single
   threading.Lock() per repository instance closes this gap.
"""

import json
import os
import threading
from datetime import date
from decimal import Decimal
from pathlib import Path

from src.domain.expense import Expense


class JsonFileExpenseRepository:
    """Concrete repository that persists expenses to a JSON file on disk."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        if not self._path.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._write([])

    def add(self, expense: Expense) -> Expense:
        with self._lock:
            records = self._read_all_raw()
            records.append(self._to_dict(expense))
            self._write(records)
        return expense

    def get_all(self) -> list[Expense]:
        with self._lock:
            return [self._from_dict(r) for r in self._read_all_raw()]

    def get_by_id(self, expense_id: str) -> Expense | None:
        with self._lock:
            for record in self._read_all_raw():
                if record["id"] == expense_id:
                    return self._from_dict(record)
        return None

    def delete(self, expense_id: str) -> None:
        with self._lock:
            records = self._read_all_raw()
            filtered = [r for r in records if r["id"] != expense_id]
            self._write(filtered)

    def _read_all_raw(self) -> list[dict]:
        """Read the raw JSON array from disk. Called only within lock."""
        text = self._path.read_text(encoding="utf-8")
        return json.loads(text)

    def _write(self, data: list[dict]) -> None:
        """Atomically write the data list to the JSON file.

        Writes to a .tmp sibling file first, then renames it into place.
        The rename (os.replace) is atomic on POSIX systems.
        """
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(data, indent=2, default=str),
            encoding="utf-8",
        )
        os.replace(tmp, self._path)

    @staticmethod
    def _to_dict(expense: Expense) -> dict:
        """Serialize an Expense domain object to a JSON-serialisable dict.

        Decimal and date are converted to str here — matching the
        default=str in _write — so that _from_dict can reconstruct them.
        """
        return {
            "id": expense.id,
            "title": expense.title,
            "amount": str(expense.amount),
            "category": expense.category,
            "date": expense.date.isoformat(),
        }

    @staticmethod
    def _from_dict(record: dict) -> Expense:
        """Deserialize a raw dict back into a typed Expense domain object.

        Uses Decimal(str) — not float — to avoid precision loss on load.
        """
        return Expense(
            id=record["id"],
            title=record["title"],
            amount=Decimal(record["amount"]),
            category=record["category"],
            date=date.fromisoformat(record["date"]),
        )
