# Smart Expense Tracker API

## Overview

A cleanly layered REST API for tracking personal expenses, built with Python 3.11+, FastAPI, and Pydantic v2. The API supports creating, listing, filtering, and deleting expenses, plus an aggregate summary endpoint. Data is persisted to a local JSON file using atomic writes — no database required. The architecture follows four strict SOLID layers (HTTP → Service → Repository → Domain), with the repository abstracted behind a `Protocol` so the production JSON backend and the in-memory test backend are fully interchangeable.

## Tech Stack

| Tool | Version | Role |
|------|---------|------|
| Python | 3.11+ | Runtime |
| FastAPI | ≥0.111 | HTTP framework, auto-generates OpenAPI/Swagger |
| Pydantic v2 | ≥2.7 | Request/response validation, type-safe DTOs |
| Uvicorn | ≥0.29 | ASGI server |
| pytest + httpx | ≥8.2 / ≥0.27 | Test framework + HTTP test client |

## Project Structure

```
Smart_Expense_Tracker_API/
├── README.md
├── AI_NOTES.md
├── requirements.txt
├── pyproject.toml
├── .gitignore
├── data/
│   └── expenses.json           # persisted data, seeded as []
├── src/
│   ├── main.py                 # app factory, exception handlers, router registration
│   ├── core/
│   │   ├── config.py           # Settings (data file path)
│   │   └── exceptions.py       # ExpenseNotFoundError, InvalidExpenseError
│   ├── domain/
│   │   └── expense.py          # Expense entity (plain dataclass, no framework imports)
│   ├── schemas/
│   │   └── expense.py          # Pydantic DTOs: ExpenseCreate, ExpenseRead, SummaryResponse
│   ├── repositories/
│   │   ├── base.py             # ExpenseRepository Protocol (4 methods only)
│   │   ├── json_file.py        # production JSON-file backend (atomic writes + Lock)
│   │   └── in_memory.py        # test backend (list-backed, no I/O)
│   ├── services/
│   │   └── expense_service.py  # business logic (depends on Protocol, not concretion)
│   └── api/
│       ├── deps.py             # DI providers (get_repository, get_service)
│       └── routes/
│           ├── expenses.py     # all 5 expense endpoints
│           └── health.py       # GET /health liveness check
└── tests/
    ├── conftest.py             # shared fixtures (in_memory_repo, test_client, ...)
    ├── unit/
    │   ├── test_schemas.py
    │   ├── test_expense_service.py
    │   └── test_json_repository.py
    └── integration/
        └── test_expense_api.py
```

## Setup & Installation

```bash
git clone <repo-url>
cd Smart_Expense_Tracker_API
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Running the Server

```bash
uvicorn src.main:app --reload --port 8000
```

Interactive docs: http://localhost:8000/docs  
Alternative docs: http://localhost:8000/redoc

## Running Tests

```bash
pytest
pytest --cov=src --cov-report=term-missing   # with coverage report
```

## API Reference

| Method | Path | Purpose | Success | Failure |
|--------|------|---------|---------|---------|
| `POST` | `/api/v1/expenses` | Create an expense | `201` + created expense | `422` invalid body |
| `GET` | `/api/v1/expenses` | List all; optional `?category=` filter | `200` + array | — |
| `GET` | `/api/v1/expenses/summary` | Overall total + breakdown by category | `200` | — |
| `GET` | `/api/v1/expenses/{id}` | Fetch one expense | `200` | `404` not found |
| `DELETE` | `/api/v1/expenses/{id}` | Delete one expense | `204` no body | `404` not found |
| `GET` | `/health` | Liveness check | `200` | — |

### Summary response shape

```json
{
  "total": "482.50",
  "count": 7,
  "by_category": {
    "Food": "210.00",
    "Transport": "150.50",
    "Utilities": "122.00"
  }
}
```

## Design Decisions & Assumptions

| Field | Decision | Rationale |
|-------|----------|-----------|
| `id` | **Server-generated** `uuid4`, never accepted from clients | Client-supplied IDs risk collisions and violate REST identity conventions. The server owns resource identity. |
| `amount` | `Decimal` with `gt=0`, `decimal_places=2`, `max_digits=12` — **never `float`** | Floats introduce silent rounding errors in summations (`0.1 + 0.2 ≠ 0.3`). `Decimal` arithmetic is exact, which is a hard requirement for any monetary calculation. |
| `category` | `str` (not `Enum`), normalised to `.strip().title()` | The assignment defines no fixed category set. An `Enum` would silently reject valid user categories. Title-casing prevents `"food"` and `"Food"` from appearing as two separate buckets in summary breakdowns. |
| `title` | `str`, stripped of leading/trailing whitespace, 1–200 chars | Blank-after-strip titles are rejected explicitly in the validator, not just by `min_length` (which passes `"   "` before stripping). |
| `date` | `date` (ISO 8601 `YYYY-MM-DD`), no future-date restriction | Some expense trackers log planned spend. No restriction is documented as an explicit assumption rather than silently guessed. |
| Persistence | Atomic write (`os.replace`) + `threading.Lock` | Atomic renames prevent corrupted JSON on mid-write crashes. The lock prevents a race condition where two concurrent FastAPI threadpool threads interleave a read-modify-write cycle. |
| Repository interface | `typing.Protocol` (structural subtyping), not `ABC` | Concrete classes don't need to import or inherit from the base. They satisfy the interface purely by shape — cleaner DIP with less coupling. |
