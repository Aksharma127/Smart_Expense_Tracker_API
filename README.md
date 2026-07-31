# Smart Expense Tracker API

A REST API for tracking expenses — create, list, filter, delete, and get category-wise summaries. Built with FastAPI and Pydantic v2, persisted to a plain JSON file (no database).

The codebase is split into four layers (routes → service → repository → domain), each with a single job. The repository is behind a `Protocol`, so swapping the JSON backend for an in-memory one in tests is a one-liner.

## Stack

- **Python 3.11+** / **FastAPI** / **Pydantic v2**
- **Uvicorn** as the ASGI server
- **pytest** + **httpx** for testing
- No database — data lives in `data/expenses.json`

## Setup

```bash
git clone <repo-url>
cd Smart_Expense_Tracker_API
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn src.main:app --reload --port 8000
```

Swagger UI → http://localhost:8000/docs
ReDoc → http://localhost:8000/redoc

## Tests

```bash
pytest
pytest --cov=src --cov-report=term-missing
```

85 tests, 99% coverage. Unit tests hit schemas, service logic, and the JSON repository independently. Integration tests exercise every endpoint through `TestClient`.

## Endpoints

```
POST   /api/v1/expenses          → 201  Create an expense
GET    /api/v1/expenses          → 200  List all (filter: ?category=Food)
GET    /api/v1/expenses/summary  → 200  Totals overall + by category
GET    /api/v1/expenses/{id}     → 200  Fetch one
DELETE /api/v1/expenses/{id}     → 204  Delete one
GET    /health                   → 200  Liveness check
```

Summary looks like this:

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

## Project Layout

```
src/
├── main.py                 # FastAPI app, exception handlers
├── core/
│   ├── config.py           # data file path
│   └── exceptions.py       # ExpenseNotFoundError
├── domain/
│   └── expense.py          # plain dataclass, no framework deps
├── schemas/
│   └── expense.py          # Pydantic DTOs (create / read / summary)
├── repositories/
│   ├── base.py             # ExpenseRepository Protocol
│   ├── json_file.py        # JSON file backend (atomic writes + Lock)
│   └── in_memory.py        # list-backed backend for tests
├── services/
│   └── expense_service.py  # business logic
└── api/
    ├── deps.py             # dependency injection wiring
    └── routes/
        ├── expenses.py
        └── health.py
```

## Design Decisions

These are the calls I made where the spec was ambiguous, and why:

**`Decimal` for money, not `float`.** Python floats are IEEE 754 binary — `0.1 + 0.2` gives `0.30000000000000004`. That's a bug in a summary endpoint. `Decimal` does exact arithmetic. The JSON round-trip stores amounts as strings (`"12.50"`) and reconstructs them with `Decimal()`, so precision is never lost.

**Server-generated UUIDs.** The `id` field is created by the service layer via `uuid4()`. It's never accepted in the POST body. Client-supplied IDs invite collisions and break REST conventions around server-owned identity.

**Categories are strings, not enums.** The spec doesn't define a fixed category list, so locking it to an enum would reject categories the user considers valid. Instead, categories are normalised with `.strip().title()` so "food", "Food", and "FOOD" all collapse to "Food" in the summary.

**Atomic writes.** The JSON repository writes to a `.tmp` file first, then does `os.replace()` (which wraps POSIX `rename(2)` — atomic). If the process dies mid-write, you get an orphaned temp file, not a corrupted `expenses.json`.

**Thread lock.** FastAPI dispatches sync handlers to a thread pool. Two concurrent POSTs without a lock can both read the file before either writes, silently dropping one write. A `threading.Lock()` around every read-modify-write cycle prevents that.

**No future-date restriction on `date`.** Some people log planned expenses. I documented this as an assumption instead of silently guessing either way.
