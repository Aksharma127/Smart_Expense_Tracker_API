"""Dependency injection providers for FastAPI.

get_repository is the seam that tests override via app.dependency_overrides.
Overriding it causes get_service to automatically receive the injected repo,
so tests never touch the real data/expenses.json file.
"""

from typing import Annotated

from fastapi import Depends

from src.core.config import settings
from src.repositories.json_file import JsonFileExpenseRepository
from src.services.expense_service import ExpenseService


def get_repository() -> JsonFileExpenseRepository:
    """Return the production JSON-file-backed repository."""
    return JsonFileExpenseRepository(settings.DATA_FILE_PATH)


def get_service(
    repo: Annotated[JsonFileExpenseRepository, Depends(get_repository)],
) -> ExpenseService:
    """Return an ExpenseService wired to the current repository."""
    return ExpenseService(repo)
