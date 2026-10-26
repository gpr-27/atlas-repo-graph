# How Atlas decides verification states

Atlas reports one of four honest states for each consumer repo: **pass**, **fail**, **not_run**, **unknown**.

## The rules

`decide_state(confidence, contract, tests)` in `atlas/verify.py` applies these in order; the first match wins:

1. confidence is `inferred` -> **unknown** (never pass or fail on a guess)
2. contract is `fail` **or** tests are `fail` -> **fail**
3. tests are `pass` -> **pass**
4. contract is `pass` and tests are `not_run` -> **not_run**
5. anything else -> **unknown**

**Invariant (NFR-006):** `state == "pass"` is only possible when confidence is `exact` **and** tests actually ran and passed. The contract may be `pass` or `n/a`.

## The cases covered by `test_decide_state`

| Confidence | Contract | Tests    | State    |
|-----------|----------|----------|----------|
| inferred  | fail     | pass     | unknown  |
| inferred  | pass     | pass     | unknown  |
| exact     | fail     | not_run  | fail     |
| exact     | pass     | fail     | fail     |
| exact     | pass     | pass     | **pass** |
| exact     | pass     | not_run  | not_run  |
| exact     | n/a      | not_run  | unknown  |
| exact     | pass     | unknown  | unknown  |

## What each field means

**Confidence** — how certain Atlas is that this consumer actually uses the producer field:
- `exact` — the same file that references the field also makes an HTTP call to an endpoint that exposes it. After a rename the old field no longer exists, so the same proof is accepted when the file calls an endpoint that exposes the old **or** the new name. A call to an endpoint that exposes neither does not count.
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
