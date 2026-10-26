# How Atlas decides verification states

Atlas reports one of four honest states for each consumer repo: **pass**, **fail**, **not_run**, **unknown**.

## The decision table

| Confidence | Contract | Tests    | State    |
|-----------|----------|----------|----------|
| inferred  | any      | any      | unknown  |
| exact     | fail     | any      | fail     |
| exact     | pass     | fail     | fail     |
| exact     | pass     | pass     | **pass** |
| exact     | pass     | not_run  | not_run  |
| exact     | n/a      | not_run  | unknown  |
| exact     | pass     | unknown  | unknown  |

**Rule:** `state == "pass"` is only possible when confidence is `exact`, contract is `pass`, and tests actually ran and passed (NFR-006).

## What each field means

**Confidence** — how certain Atlas is that this consumer actually uses the producer field:
- `exact` — the same file that references the field also makes an HTTP call to the endpoint that exposes it (or a CALLS edge proves it).
- `inferred` — the field name matches, but no explicit HTTP call links the repos. Atlas cannot be sure.

**Contract** — does the producer still expose what the consumer expects?
- `pass` — the producer still exposes the field (or the consumer was updated to the new name).
- `fail` — the consumer still references `symbol` but no producer exposes it any more.
- `n/a` — there is nothing to check (e.g. consumer only references the new name and the old name was never exposed to it).

**Tests** — what happened when the consumer repo's tests were run:
- `pass` — `test_cmd` ran and exited 0.
- `fail` — `test_cmd` ran and exited non-zero.
- `not_run` — `--run-tests` was not passed, or no test command was detected.
- `unknown` — the test command timed out or failed to start.

## The reason string

Format: `[name match only; ]<contract reason>[; tests: <detail>]`

Examples:
- `still references customer_id, which no producer exposes` (exact, fail contract)
- `name match only; still references customer_id, which no producer exposes` (inferred)
- `updated to account_id` (exact, pass — consumer was updated)
- `customer_id still exposed` (exact, pass — no rename)
