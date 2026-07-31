# AI Notes

## What I used

Claude (Sonnet) for the initial architecture discussion, boilerplate scaffolding, and first-pass implementations of each layer. Everything was reviewed and tested before committing. Below are the places where the AI output needed real intervention — not just cosmetic tweaks, but changes that would've caused bugs or design problems if I'd shipped the draft as-is.

## Where AI got it right without changes

The domain entity (`expense.py` — a plain dataclass), the exceptions module, the config, and the `InMemoryExpenseRepository` all came out clean on the first pass. Simple stuff. The `Protocol`-based repository interface was also correct — I just verified it only exposed the four methods we actually need (`add`, `get_all`, `get_by_id`, `delete`) and didn't bloat into a generic CRUD base.

## Where I had to step in

### The `float` → `Decimal` fix

The first draft of the Pydantic schema used `float` for the `amount` field. That's the kind of thing that works in a demo and breaks in production. Python's `float` is IEEE 754 binary, so `0.1 + 0.2` evaluates to `0.30000000000000004` — which means the `/summary` endpoint would return slightly wrong totals once you have enough expenses. Switched it to `Decimal` with `decimal_places=2` and `max_digits=12`.

This wasn't just a schema change — it rippled through the whole persistence layer. The JSON repository serialises amounts as strings (`str(expense.amount)`) and reconstructs them with `Decimal(record["amount"])`, never going through `float()` at any point. I wrote a specific test (`test_summary_decimal_precision`) that sums `0.10 + 0.20` and asserts the result is exactly `0.30`, because that's the test that would've caught the original bug.

### Atomic writes and the thread lock

The AI's first version of `JsonFileExpenseRepository._write()` was a bare `path.write_text(json.dumps(data))`. Two problems with that:

1. If the process gets killed mid-write, you end up with a half-written JSON file that `json.loads()` can't parse on the next startup. The fix: write to `expenses.tmp` first, then `os.replace(tmp, path)`. `os.replace` wraps `rename(2)` on POSIX, which is atomic — the old file is either fully there or fully replaced, never half-and-half.

2. FastAPI runs sync route handlers in a thread pool. Without a lock, two concurrent POST requests can both read the file, both append their expense, and both write back — except the second write overwrites the first, silently losing data. A `threading.Lock()` around every read-modify-write cycle closes this.

Neither of these showed up in the AI's output. They came from thinking about "what breaks under real concurrency" and "what happens if the server crashes."

### Route ordering — the `/summary` bug

This was a subtle one. The AI registered `/{expense_id}` before `/summary` in the router. FastAPI matches routes in order, so a request to `GET /expenses/summary` would match `/{expense_id}` first, bind `expense_id = "summary"`, look it up, fail, and return a 404.

The fix was straightforward — register `/summary` before `/{expense_id}` — but the real lesson is that this kind of bug is completely silent. It doesn't throw an error, it just routes to the wrong handler. I added a regression test (`test_summary_route_not_captured_as_id_param`) specifically so that if anyone reorders these routes later, the test suite catches it immediately instead of the bug sitting there until a user files a ticket.

### Whitespace-only title edge case

The AI's test suite didn't cover posting a title that's just spaces (`"   "`). The `min_length=1` constraint on the Pydantic field passes `"   "` because it has 3 characters — but after `.strip()` it's empty. I added an explicit check in the `@field_validator` to reject blank-after-strip titles, and a matching test.

## What I said no to

**SQLite / SQLAlchemy** — The AI suggested it. The assignment explicitly says no database is required, and the JSON file handles everything at this scale. Adding an ORM would've tripled the codebase for zero grading benefit.

**Generic `Repository[T]`** — The AI wanted to build an abstract base that could handle any entity type. There's one entity. I used a `Protocol` with four specific methods instead.

**Pagination, sorting, PUT endpoint** — None of these are in the spec. Adding them would've meant more surface area to test and document, with no upside.

**Custom 422 handler** — FastAPI's default validation error response is already well-structured. Replacing it just to "own" the error format would've been busywork.

**Docker / CI** — I picked the OpenAPI bonus. Building Docker on top of that doesn't earn extra marks and eats into time better spent on code quality.
