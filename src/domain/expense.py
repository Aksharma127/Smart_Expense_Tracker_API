"""Domain entity for an expense.

Deliberately framework-agnostic: no Pydantic, no FastAPI imports.
This is the core type that every other layer operates on.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class Expense:
    """Represents a single recorded expense.

    Fields:
        id:       Server-generated UUID string. Never accepted from clients.
        title:    Human-readable description of the expense.
        amount:   Monetary value. Stored as Decimal to avoid float rounding errors.
        category: Normalised (title-cased) category string.
        date:     ISO 8601 date of the expense.
    """

    id: str
    title: str
    amount: Decimal
    category: str
    date: date
