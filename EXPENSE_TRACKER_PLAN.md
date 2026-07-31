# Smart Expense Tracker API — Build Plan
**Stack:** Python 3.11+ / FastAPI · **Bonus:** OpenAPI/Swagger polish · **Time budget:** ~7–8 focused hours inside your 48-hour window

---

## 0. What "winning" actually means here

This isn't graded on feature count — it's a 4-hour assignment stretched to 48 hours specifically to see what you do with the slack. Two things separate a top submission from an average one:

1. **Judgment, not volume.** A tightly-scoped, cleanly layered, well-tested API beats a bloated one every time. Don't add auth, a database, pagination, or five abstraction layers nobody asked for — that reads as *not knowing what "done" looks like*, which is worse than under-building.
2. **An AI_NOTES.md that shows real engineering thinking.** They told you this costs marks if generic. Graders can spot a copy-pasted "AI helped me write boilerplate, I reviewed it" from a mile away. Yours needs specifics: what you changed and *why*, in your own words, tied to real lines of code.

Everything below is scoped to hit both without turning a simple CRUD API into a science project. If a section ever feels like it's adding ceremony for its own sake — skip it. That instinct is correct.

---

## 1. Tech stack & why

| Choice | Reason |
|---|---|
| **FastAPI** | Async-ready, Pydantic-native validation, auto-generates OpenAPI/Swagger (your bonus) for free |
| **Pydantic v2** | Type-safe request/response models, built-in validators |
| **Uvicorn** | Standard ASGI server for FastAPI |
| **pytest + httpx (TestClient)** | Industry-standard, integrates cleanly with FastAPI |
| **Plain JSON file** | Assignment explicitly allows this — no DB needed, no ORM ceremony |

Don't add SQLAlchemy, SQLite, or an ORM. It's tempting because it "looks more enterprise," but it directly contradicts the assignment's "no database required" line and adds nothing the JSON approach can't do at this scale.

---

## 2. Architecture — layered, SOLID, proportional

Four thin layers, each with one job. This is the whole "enterprise" trick: not more code, just code that's separated correctly.

```
HTTP Layer (FastAPI routes)
        ↓ depends on
Service Layer (business logic — filtering, totals, validation orchestration)
        ↓ depends on (abstraction, not concretion)
Repository Layer (persistence — JSON file read/write)
        ↓ operates on
Domain Layer (Expense entity — plain, framework-agnostic)
```

**SOLID mapping (so you can name-drop this correctly in AI_NOTES.md):**

- **SRP** — routers only handle HTTP concerns; services only handle business rules; repositories only handle persistence.
- **OCP** — you can add a new storage backend (e.g. in-memory for tests) without touching the service layer.
- **LSP** — `JsonFileExpenseRepository` and `InMemoryExpenseRepository` are interchangeable wherever `ExpenseRepository` is expected.
- **ISP** — the repository interface only exposes the four methods actually used (`add`, `get_all`, `get_by_id`, `delete`) — not a bloated generic CRUD interface.
- **DIP** — `ExpenseService` depends on an abstract `ExpenseRepository` (a `Protocol`), not the concrete JSON implementation. FastAPI's dependency injection wires the concrete class in at runtime.

This is genuinely useful architecture for this problem size — not overkill. Four small layers, ~150–250 lines total in `src/`.

---

## 3. Folder structure

```
expense-tracker-api/
├── README.md
├── AI_NOTES.md
├── requirements.txt
├── pyproject.toml              # pytest/ruff config (optional but cheap polish)
├── .gitignore
├── data/
│   └── expenses.json           # persisted data, seeded as []
├── src/
│   ├── __init__.py
│   ├── main.py                 # app factory, exception handlers, router registration
│   ├── core/
│   │   ├── config.py            # Settings (data file path, etc.)
│   │   └── exceptions.py        # ExpenseNotFoundError, InvalidExpenseError
│   ├── domain/
│   │   └── expense.py           # Expense entity (plain dataclass)
│   ├── schemas/
│   │   └── expense.py           # Pydantic DTOs: ExpenseCreate, ExpenseRead, SummaryResponse
│   ├── repositories/
│   │   ├── base.py              # ExpenseRepository Protocol
│   │   ├── json_file.py         # concrete JSON-file implementation
│   │   └── in_memory.py         # concrete in-memory implementation (handy for fast tests)
│   ├── services/
│   │   └── expense_service.py   # business logic
│   └── api/
│       ├── deps.py              # DI providers (get_repository, get_service)
│       └── routes/
│           ├── expenses.py
│           └── health.py
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── test_schemas.py
    │   ├── test_expense_service.py
    │   └── test_json_repository.py
    └── integration/
        └── test_expense_api.py
```

No `models/`, `controllers/`, `utils/`, `helpers/` grab-bag folders. Every folder name says exactly what lives in it.

---

## 4. Domain model & validation — the decisions that show judgment

The assignment lists fields loosely (`id, title, amount, category, date`). How you resolve the ambiguity *is* the signal. Make these calls and **write them down** in your README's "Design Decisions" section:

| Field | Decision | Why |
|---|---|---|
| `id` | **Server-generated** (`uuid4`), never accepted in the POST body | Client-supplied IDs risk collisions and violate REST convention — the server owns identity |
| `amount` | `Decimal`, not `float`, with `gt=0` and 2 decimal places | Floats introduce rounding error in sums (`0.1 + 0.2 != 0.3`) — wrong for money, and worth calling out explicitly since it's an easy thing to get lazily wrong |
| `title` | `str`, 1–200 chars, stripped of whitespace | Basic hygiene |
| `category` | `str`, 1–50 chars, normalized (`.strip().title()`), **not** a hardcoded enum | Assignment doesn't define a fixed category set — an enum would silently reject valid user categories. Normalizing casing avoids `"food"` vs `"Food"` fragmenting your totals |
| `date` | `date` (ISO 8601, `YYYY-MM-DD`) | No future-date restriction by default — some expense trackers log planned spend. Document this as an assumption rather than silently guessing |

**Illustrative schema** (don't copy verbatim — write it yourself, but this is the shape):

```python
from decimal import Decimal
from datetime import date as date_type
from pydantic import BaseModel, Field, field_validator

class ExpenseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    amount: Decimal = Field(..., gt=0, decimal_places=2, max_digits=12)
    category: str = Field(..., min_length=1, max_length=50)
    date: date_type

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        return v.strip()

    @field_validator("category")
    @classmethod
    def normalize_category(cls, v: str) -> str:
        return v.strip().title()
```

`ExpenseRead` extends this with `id: str`. Keep `ExpenseCreate` (input, no id) and `ExpenseRead` (output, with id) as separate models — this alone is a small but real signal of API design maturity.

---

## 5. API contract

| Method | Path | Purpose | Success | Failure |
|---|---|---|---|---|
| `POST` | `/api/v1/expenses` | Create an expense | `201` + created expense | `422` invalid body |
| `GET` | `/api/v1/expenses` | List all, optional `?category=` filter | `200` + array | `422` malformed query |
| `GET` | `/api/v1/expenses/{id}` | Fetch one (not required, but completes the REST shape cheaply) | `200` | `404` |
| `DELETE` | `/api/v1/expenses/{id}` | Delete one | `204` no body | `404` |
| `GET` | `/api/v1/expenses/summary` | Overall total + breakdown by category | `200` | — |
| `GET` | `/health` | Liveness check | `200` | — |

**Why one `/summary` endpoint instead of two separate total endpoints:** it satisfies "overall and by category" in a single, cacheable, REST-clean call:

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

Filtering by category reuses the *existing* list endpoint via query param (`GET /expenses?category=Food`) rather than a separate `/expenses/by-category/{cat}` route — one endpoint, one responsibility, less surface area to test and document. This is the kind of small consolidation worth a line in AI_NOTES.md if AI originally generated two separate endpoints and you merged them.

Skip pagination, sorting params, and bulk endpoints — not asked for, and they'd bloat the contract without adding grading value.

---

## 6. Error handling

Two custom exceptions, mapped centrally so every error response has the same shape:

```python
# core/exceptions.py
class ExpenseNotFoundError(Exception):
    def __init__(self, expense_id: str):
        self.expense_id = expense_id

class InvalidExpenseError(Exception):
    pass
```

```python
# main.py
@app.exception_handler(ExpenseNotFoundError)
async def not_found_handler(request, exc: ExpenseNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"error": "not_found", "message": f"Expense '{exc.expense_id}' not found"},
    )
```

Let Pydantic's built-in `422` validation errors pass through unmodified — FastAPI's default shape is already good, and reinventing it wastes time for no grading benefit.

---

## 7. Persistence — JSON file, done properly

Two details separate "I wrote to a JSON file" from "I thought about what could go wrong":

1. **Atomic writes** — write to a temp file, then `os.replace()` into place. If the process dies mid-write, you never end up with a half-written, corrupted `expenses.json`.
2. **A lock around read-modify-write** — FastAPI runs sync path functions in a threadpool, so concurrent requests *can* race on file I/O even with one Uvicorn worker. A single `threading.Lock()` in the repository around each write closes this gap.

```python
# repositories/json_file.py (skeleton — you implement the body)
import json, os, threading
from pathlib import Path

class JsonFileExpenseRepository:
    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()
        if not self._path.exists():
            self._write([])

    def _write(self, data: list[dict]) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str))
        os.replace(tmp, self._path)   # atomic on POSIX and Windows
```

This is the single highest-signal-per-line detail in the whole project — it's the kind of thing that separates "worked in the demo" from "thought about production." Definitely mention it in AI_NOTES.md if AI's first draft didn't include it.

---

## 8. Testing strategy

Aim for the layers to be independently testable — that's the payoff of the DIP-based design.

| Layer | What to test | How |
|---|---|---|
| **Schemas (unit)** | Rejects negative/zero amount, empty title, missing fields, malformed date | Direct Pydantic instantiation, assert `ValidationError` |
| **Service (unit)** | Filtering logic, summary math, delete-not-found raises | Inject `InMemoryExpenseRepository` (fast, no disk I/O) |
| **JSON repository (unit)** | Persists across reload, atomic write survives a simulated crash, empty-file bootstrap | `pytest`'s `tmp_path` fixture — never touch the real `data/` dir in tests |
| **API (integration)** | Full request/response cycle for every endpoint in section 5, including 404s and 422s | `httpx`/FastAPI `TestClient`, with the repository dependency overridden to a temp file |

Specific edge cases worth naming explicitly (and worth a line in AI_NOTES.md — "AI's first test suite didn't cover this, I added it"):
- Deleting a non-existent id → `404`, not a silent no-op
- Filtering by a category with zero matches → `200` + empty array, not `404`
- Category filter is case-insensitive (`?category=food` matches `"Food"`)
- Summary on an empty dataset → `total: "0.00"`, `by_category: {}`, not a crash

Run with:
```bash
pytest --cov=src --cov-report=term-missing
```

---

## 9. Bonus: OpenAPI/Swagger polish

FastAPI gives you `/docs` and `/redoc` for free — the bonus is making them *actually good*, which costs about 20 minutes:

- Add `summary` and `description` to each route decorator (`@router.post("/", summary="Create a new expense", ...)`)
- Add `response_model=ExpenseRead` and correct `status_code` on every route
- Add `json_schema_extra` examples on your Pydantic models so the "Try it out" panel pre-fills sensible sample data
- Set `title`, `description`, `version` on the `FastAPI()` app instance itself

This is the cheapest possible bonus given your stack — treat it as a checklist, not a project.

---

## 10. What to deliberately leave out

Naming what you *didn't* build, and why, is one of the strongest signals you can put in AI_NOTES.md — it shows scope discipline, not just execution. Deliberately skip:

- Authentication / API keys — not asked for, adds no grading value
- A real database — explicitly not required
- Pagination / sorting — out of scope for the listed requirements
- Generic repository interfaces designed for hypothetical future entities beyond `Expense`
- Docker, CI, and the other three bonus options — you picked one; building a second doesn't earn extra credit and burns your time budget

If you used AI and it suggested any of these unprompted, that's exactly the "AI suggestion I decided not to use" material they're asking for.

---

## 11. 48-hour execution plan (actual work: ~7–8 hrs)

Spread across your 48 hours in whatever sessions fit your schedule — don't grind it in one sitting, and don't feel pressure to fill all 48 hours with work.

| Session | Time | Output |
|---|---|---|
| 1 | 45 min | Repo scaffold, folder structure, `requirements.txt`, git init, first commit |
| 2 | 1.5 hr | Domain entity + repository `Protocol` + `JsonFileExpenseRepository` + its unit tests |
| 3 | 1.5 hr | `ExpenseService` (business logic) + unit tests against `InMemoryExpenseRepository` |
| 4 | 1 hr | FastAPI routers, Pydantic schemas, DI wiring in `deps.py`, exception handlers |
| 5 | 1 hr | Integration tests covering every endpoint + edge cases from §8 |
| 6 | 30 min | OpenAPI polish (§9) |
| 7 | 30 min | Write README.md, then **verify every command on a truly clean checkout** (fresh clone or fresh venv) |
| 8 | 30–45 min | Write AI_NOTES.md from your running notes (see §13 — keep notes *as you go*, don't reconstruct from memory) |
| Buffer | remaining time | `ruff`/`black` pass, re-read your own code cold, final clean-checkout test |

**Keep a scratch file open the whole time** (not part of the submission) where you jot one line every time AI generates something you changed, rejected, or had to fix. This is what makes §13 write itself instead of becoming generic filler at the end.

---

## 12. README.md template

```markdown
# Smart Expense Tracker API

## Overview
[2-3 sentences: what it does, the stack, why you made the key design calls]

## Tech Stack
- Python 3.11+, FastAPI, Pydantic v2, Uvicorn
- pytest + httpx for testing

## Project Structure
[paste the tree from section 3]

## Setup & Installation
\`\`\`bash
git clone <repo-url>
cd expense-tracker-api
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
\`\`\`

## Running the Server
\`\`\`bash
uvicorn src.main:app --reload --port 8000
\`\`\`
Interactive docs: http://localhost:8000/docs

## Running Tests
\`\`\`bash
pytest
pytest --cov=src --cov-report=term-missing   # with coverage
\`\`\`

## API Reference
[table from section 5, or "see /docs for full interactive reference"]

## Design Decisions & Assumptions
[the table from section 4, in prose — this is where judgment shows]
```

**Test these exact commands on a clean checkout before you submit.** The brief says they'll run them verbatim — a typo here costs you the whole automated review, regardless of code quality.

---

## 13. AI_NOTES.md — how to make this your strongest section

Don't write this from memory at the end. Use the running scratch notes from §11. Structure:

```markdown
# AI Notes

## Tools used
[e.g. Claude for architecture/scaffolding discussion and boilerplate generation]

## AI-generated vs hand-written
| Component | Origin |
|---|---|
| Repository Protocol + JSON implementation skeleton | AI-drafted, I added the atomic-write + lock logic |
| ExpenseService business logic | Hand-written |
| Pydantic schemas | AI-drafted, I changed amount from float to Decimal |
| Test suite structure | AI-drafted, I added the edge cases in [section] |

## What I validated, tested, or changed, and why
- [Specific example, tied to a real change — e.g. "AI's first repository draft used float
  for amount; I switched to Decimal with a 2-decimal-place constraint after confirming
  Pydantic v2 supports it natively, because float addition produces rounding errors in
  the summary totals (verified with a test summing 0.1 + 0.2-style values)."]
- [Another specific example — persistence, validation, or test coverage]

## AI suggestions I rejected, and why
- [e.g. "AI suggested SQLite for persistence — rejected, the brief explicitly said no DB
  is required and JSON meets the need with less setup complexity."]
- [e.g. "AI proposed a generic Repository<T> with a plugin registry for future entity
  types — rejected as overengineered; there's only one entity in this domain."]
```

The grading note says a generic AI_NOTES.md costs marks *even with solid code*. The difference between generic and strong is entirely in specificity — name real files, real lines, real reasoning. Two or three genuinely specific examples beat ten vague ones.

---

## 14. Cheap extra polish (optional, low time cost)

- `.gitignore` covering `venv/`, `__pycache__/`, `.pytest_cache/`
- Pin `requirements.txt` versions via `pip freeze > requirements.txt` after installing
- A handful of small, well-described commits instead of one giant commit — tells a story of how you built it
- `ruff` + `black` for a quick lint/format pass (a few minutes, looks deliberate)
- A `.github/workflows/ci.yml` running `pytest` on push — genuinely optional, but if you have spare time it's a strong, low-risk signal of engineering habit (it isn't one of the four listed bonuses, so it doesn't compete with your OpenAPI pick — it's just hygiene)

---

## 15. Pre-submission checklist

- [ ] Fresh clone / fresh venv → README commands work exactly as written, no hidden steps
- [ ] `pytest` passes clean, no skipped/xfail tests
- [ ] All 5 required features work via `/docs` manually: add, list all, filter by category, totals (overall + by category), delete
- [ ] `AI_NOTES.md` has specific, real examples — not "AI helped me write the code and I reviewed it"
- [ ] No stray `print()` debugging statements or commented-out dead code
- [ ] `data/expenses.json` either gitignored or committed as a clean seed (`[]`) — not left full of your test data
