# AI Notes

## Tools Used

- **Claude Sonnet 4.6 (Thinking)** — used for architecture discussion, scaffolding, boilerplate generation, and iterative implementation of all layers.
- All AI-generated output was reviewed, corrected, and validated before being committed. Several components required deliberate intervention to meet production standards; those decisions are documented below.

---

## AI-Generated vs. Hand-Written

| Component | Origin | Notes |
|-----------|--------|-------|
| `src/domain/expense.py` | AI-drafted | No changes required — plain dataclass with no framework dependencies |
| `src/core/exceptions.py` | AI-drafted | No changes required |
| `src/core/config.py` | AI-drafted | No changes required |
| `src/repositories/base.py` (Protocol) | AI-drafted | Reviewed and confirmed: 4 methods only (ISP enforcement) |
| `src/repositories/json_file.py` | AI-drafted skeleton, **human-enforced** production details | Atomic write (`os.replace`) and `threading.Lock` were explicitly required — see §3 below |
| `src/repositories/in_memory.py` | AI-drafted | `get_all()` returns `list(self._store)` (copy) — ensured by review to prevent caller mutation of internal state |
| `src/schemas/expense.py` | AI-drafted, **human-corrected** on `amount` type | AI initially defaulted to `float`; changed to `Decimal` with `decimal_places=2` — see §1 below |
| `src/services/expense_service.py` | AI-drafted | `delete_expense` reviewed to confirm it raises `ExpenseNotFoundError` and is not a silent no-op |
| `src/api/routes/expenses.py` | AI-drafted, **human-corrected** on route order | `/summary` registration before `/{expense_id}` was a required manual fix — see §4 below |
| `src/main.py` | AI-drafted | Reviewed exception handler shape for consistency |
| `tests/unit/test_schemas.py` | AI-drafted | Added explicit `test_whitespace_only_rejected` — AI's first draft didn't cover blank-after-strip |
| `tests/unit/test_expense_service.py` | AI-drafted | Added `test_summary_decimal_precision` (the `0.1+0.2=0.30` invariant) — AI's first pass omitted this critical edge case |
| `tests/integration/test_expense_api.py` | AI-drafted | Added `test_summary_route_not_captured_as_id_param` to catch the route-order bug if it ever regresses |

---

## What I Validated, Tested, or Changed, and Why

### 1. Data Integrity: `float` → `Decimal` for monetary amounts

AI's initial draft of `src/schemas/expense.py` defined the amount field as:

```python
amount: float = Field(..., gt=0)
```

This was changed to:

```python
amount: Decimal = Field(..., gt=0, decimal_places=2, max_digits=12)
```

**Why it matters:** Python's `float` uses IEEE 754 binary representation. `0.1 + 0.2` evaluates to `0.30000000000000004`, not `0.3`. In the `get_summary()` method in `expense_service.py`, amounts are summed across all expenses. A user with several transactions would receive a subtly incorrect `total` in the summary response. This is a correctness failure in a financial application — not a style issue.

Pydantic v2 supports `Decimal` natively with `decimal_places` and `max_digits` constraints (verified against v2 docs before using). The `_to_dict` / `_from_dict` serialization in `json_file.py` stores Decimal as `str(amount)` and reconstructs with `Decimal(record["amount"])` — not `float(record["amount"])` — to preserve exactness through the JSON round-trip.

This was validated explicitly with `test_summary_decimal_precision` in `test_expense_service.py`, which asserts that `Decimal("0.10") + Decimal("0.20") == Decimal("0.30")` through the full service stack.

---

### 2. Concurrency & Safety: Atomic writes and thread lock in `JsonFileExpenseRepository`

AI's initial repository implementation performed a straightforward `path.write_text(json.dumps(data))`. Two production-grade concerns were added:

**a) Atomic write via `os.replace()`** (`json_file.py`, `_write` method):

```python
def _write(self, data: list[dict]) -> None:
    tmp = self._path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, self._path)
```

`os.replace()` wraps the POSIX `rename(2)` syscall, which is atomic. If the process is killed mid-write, the `.tmp` file is left orphaned — the real `expenses.json` is never left in a partially-written, corrupted state. A direct `write_text()` has no such guarantee.

**b) `threading.Lock()` around every read-modify-write cycle:**

FastAPI dispatches synchronous path functions to a thread pool executor (`asyncio.get_event_loop().run_in_executor`). With a single Uvicorn worker, two concurrent POST requests can both read the file before either writes back, causing one write to silently overwrite the other. A module-level `threading.Lock()` serialises all write operations within a process, closing this race.

Neither of these details appeared in AI's first draft. Both were explicitly added after reviewing what could go wrong in a concurrent server context.

---

### 3. Scope Discipline: Rejecting SQLite, ORM, and over-engineered abstractions

AI suggested two additions that were explicitly rejected:

**a) SQLite via SQLAlchemy:**

> "AI suggested replacing the JSON file with a SQLite database backed by SQLAlchemy for more robust querying."

Rejected. The assignment's brief explicitly states "no database required." Adding SQLAlchemy would introduce ~300 lines of ORM models, sessions, migrations boilerplate, and a new dependency with no grading benefit. The JSON file, done with atomic writes and a lock, meets all functional requirements at this scale. Adding a database here reads as not knowing what "done" looks like.

**b) Generic `Repository[T]` with a plugin registry:**

> "AI proposed abstracting the repository interface as `Repository[Generic[T]]` with a registry pattern to support future entity types."

Rejected. There is exactly one entity in this domain (`Expense`). A generic repository for hypothetical future entities is speculative abstraction that adds complexity without value. The `Protocol` approach used (`ExpenseRepository` with 4 specific methods) satisfies ISP and OCP for the actual problem size. The `JsonFileExpenseRepository` and `InMemoryExpenseRepository` are interchangeable for `Expense` exactly — nothing more is needed.

---

### 4. Framework Expertise: Route registration order for `/summary` vs `/{id}`

AI's initial draft of `src/api/routes/expenses.py` registered the routes in CRUD order:

```python
# AI's first draft (WRONG ORDER)
@router.get("/{expense_id}", ...)   # registered first
@router.get("/summary", ...)        # registered second — NEVER REACHED
```

FastAPI (via Starlette) matches routes in **registration order**. With the above order, a `GET /api/v1/expenses/summary` request matches `/{expense_id}` first, binding `expense_id = "summary"`, and routes to `get_expense("summary")` — which returns a `404 not found` instead of the summary.

The fix was to register `/summary` explicitly before `/{expense_id}`:

```python
# Correct order (expenses.py, lines 52–62)
# /summary MUST come before /{expense_id} — see module docstring.
@router.get("/summary", ...)        # registered first — matches literal "summary"
@router.get("/{expense_id}", ...)   # registered second — captures dynamic IDs
```

A regression test was added specifically for this (`test_summary_route_not_captured_as_id_param` in `test_expense_api.py`) so any future reordering immediately causes a test failure rather than a silent routing bug.

---

## AI Suggestions I Rejected, and Why

| Suggestion | Decision | Reason |
|-----------|----------|--------|
| `float` for `amount` | ❌ Rejected, changed to `Decimal` | Float arithmetic is incorrect for money; `0.1+0.2 ≠ 0.3` would corrupt summary totals |
| SQLite + SQLAlchemy for persistence | ❌ Rejected | Assignment explicitly says no database; adds complexity with no functional benefit |
| Generic `Repository[T]` abstraction | ❌ Rejected | Only one entity exists; speculative generics add ceremony without value |
| Registering `/{id}` before `/summary` | ❌ Rejected (corrected) | Would cause FastAPI to route `/summary` as a dynamic ID lookup, returning 404 |
| Pagination and sorting parameters | ❌ Rejected | Not in the assignment requirements; would bloat the API surface and test scope |
| Docker and CI workflow | ❌ Rejected | Only one bonus (OpenAPI) was selected; building extras burns time without earning extra credit |
| `PUT /expenses/{id}` update endpoint | ❌ Rejected | Not in the specified API contract (§5 of the plan); adding it is scope creep |
| `@app.exception_handler` for `422` | ❌ Rejected | FastAPI's default 422 shape is already correct; reinventing it wastes effort with no benefit |
