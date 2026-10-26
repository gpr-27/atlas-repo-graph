# Atlas example workspace

Four tiny repos that reproduce the demo end-to-end.

| Repo | Role | What it does |
|---|---|---|
| `backend/` | Producer | FastAPI-style app + OpenAPI spec exposing `GET /users/{user_id}` with fields `id`, `customer_id`, `email` |
| `billing/` | Consumer (exact) | Calls the backend with `urlopen`, reads `customer_id` |
| `web/` | Consumer (exact) | Calls the backend with `urlopen`, reads `customer_id` and `email` |
| `analytics/` | Consumer (inferred) | Reads `customer_id` from a CSV file — no HTTP call, so link is inferred |

## Running the demo

```bash
bash examples/demo.sh
```

The script:
1. Scans all four repos
2. Shows `atlas impact customer_id`
3. Renames `customer_id` → `account_id` in backend and web (billing and analytics are **not** updated)
4. Re-scans
5. Runs `atlas verify customer_id --renamed-to account_id --run-tests`
6. Resets the files with `git checkout`

## Expected verify output (step 5)

```
Consumer   Evidence       Confidence  Contract  Tests    State    Reason
---------  -------------  ----------  --------  -------  -------  ------------------------------------------------------------------------
analytics  report.py:6    inferred    fail      not_run  unknown  name match only; still references customer_id, which no producer exposes
billing    charge.py:10   exact       fail      fail     fail     still references customer_id, which no producer exposes
web        profile.py:10  exact       pass      pass     pass     updated to account_id
pass=1  fail=1  not_run=0  unknown=1
```

- **billing** → `fail`: still calls `customer_id` but the producer no longer exposes it; tests confirm the breakage.
- **web** → `pass`: updated to `account_id`; exact link + tests pass.
- **analytics** → `unknown`: name match only (no HTTP call), so Atlas cannot be certain; honest `unknown` beats a false green check.

## No extra packages needed

The example repos use only Python stdlib (`urllib`, `json`, `csv`) plus `pyyaml` (already installed by Atlas).
