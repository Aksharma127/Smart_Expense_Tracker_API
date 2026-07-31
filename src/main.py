"""FastAPI application factory.

Responsibilities:
  - Creates and configures the FastAPI instance (title, description, version).
  - Registers all routers.
  - Registers domain exception handlers so every error response has a
    uniform JSON shape: {"error": "<code>", "message": "<detail>"}.

Pydantic's 422 validation errors are left to FastAPI's default handler —
the default shape is already correct and reinventing it adds no value.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.api.routes import expenses, health
from src.core.exceptions import ExpenseNotFoundError

app = FastAPI(
    title="Smart Expense Tracker API",
    description=(
        "A cleanly layered REST API for tracking personal expenses. "
        "Supports creating, listing, filtering, and deleting expenses, "
        "plus an aggregate summary endpoint. "
        "Data is persisted to a local JSON file using atomic writes."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.exception_handler(ExpenseNotFoundError)
async def not_found_handler(request, exc: ExpenseNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": "not_found",
            "message": f"Expense '{exc.expense_id}' not found",
        },
    )


app.include_router(health.router)
app.include_router(expenses.router)
