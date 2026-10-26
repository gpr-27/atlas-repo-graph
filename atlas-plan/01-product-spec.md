# 01 — Product specification

## Name
**Atlas** (product). Repo/package name: **`atlas-repo-graph`** (the bare name "atlas" is taken on PyPI and GitHub).
CLI command: `atlas`. Python package: `atlas`.

## One-sentence pitch
Atlas maps how your repos depend on each other, tells you what a change will break, and proves it with file-and-line evidence — then tells you honestly what was and wasn't tested.

## Vision
Real software spans many repositories: a backend, a web client, a billing job, an analytics script. Coding agents (and humans) see one repo at a time, so a change that looks local breaks a consumer somewhere else. Atlas is the shared map: deterministic, local, inspectable, and queryable by agents over MCP.

## Target user
A developer (or small team) who:
- keeps related code in 2+ git repositories on their machine,
- uses an AI coding agent (Claude Code, Codex, Cursor, opencode, …), and
- has been bitten by "the change was fine here, it broke over there."

Secondary: the agent itself, which calls Atlas tools before editing.

## The problem
- Agents and `grep` only see the repo they're in.
- Existing code-graph tools mostly index one repo, or link across services without showing the evidence, or say "pass" when nothing ran.
- Developers want a trustworthy answer to "if I rename this field, who breaks?" and "was that actually checked?"

## Main use cases
1. **Impact before change** — `atlas impact customer_id` → every consumer, with file:line and the exact snippet, and whether the link is exact or inferred.
2. **Verify after change** — `atlas verify customer_id --renamed-to account_id --run-tests` → per consumer: contract check result, test result, and a final state in {pass, fail, not_run, unknown}, each with a reason.
3. **Agent asks first** — any MCP-capable coding agent calls `atlas_impact` / `atlas_verify` tools during a task.
4. **Explore** — `atlas status`, `atlas search users`, `atlas explain-edge 17`.

## Core value proposition
- **Cross-repo**, not single-repo.
- **Evidence on every edge** (repo, commit, file, line, snippet, extractor, confidence).
- **Four honest states** — a truthful `unknown` beats a false green check.
- **Agent-first** — MCP tools with structured output; works with any MCP-capable agent.
- **Tiny and local** — Python standard library + `pyyaml` + `mcp`; one SQLite file; no server, no account.

## Product boundaries (MVP)
In scope:
- Languages: **Python** source (via `ast`) and **OpenAPI 3.x** files (YAML/JSON).
- Producers: HTTP endpoints (FastAPI/Flask-style decorators, OpenAPI `paths`) and the response fields they expose (dict-literal returns, OpenAPI response schema properties).
- Consumers: HTTP calls (`requests.*`, `httpx.*`, `urllib.request.urlopen`) and field references (`x["f"]`, `x.get("f")`, `x.f`).
- Linking: `CALLS` (http_call → endpoint by method+path pattern), `CONSUMES` (field_ref → field, `exact` when the same file also calls the exposing endpoint, otherwise `inferred`), `EXPOSES` (endpoint → field).
- Verification: deterministic contract check (does the producer still expose the field?) + optional test run per consumer repo (auto-detected `pytest`, or `.atlas.yaml` `test_cmd`).
- Interfaces: CLI (`scan`, `status`, `impact`, `verify`, `search`, `explain-edge`, `serve`) and MCP server (`atlas_status`, `atlas_impact`, `atlas_verify`, `atlas_search`, `atlas_explain_edge`).
- Example workspace with 4 tiny repos (`backend`, `billing`, `web`, `analytics`) that reproduces the demo.

Non-goals (MVP) — see `05-full-roadmap.md`:
- Other languages (TypeScript/Go/Java), gRPC/GraphQL/events/queues, runtime tracing, DB schemas.
- A web UI or graph picture.
- Automatic code fixes.
- Hosted service, accounts, telemetry.
- Any model in the decision path.

## Assumptions (labelled)
- A1. Users run Atlas on their own machine against local clones. (Design: local-first.)
- A2. Consumers reference producer fields by literal string keys or attributes; dynamic keys are out of scope.
- A3. Running a repo's tests is safe for the user (Atlas runs the user's own test command, with a timeout).
- A4. The user's agent supports MCP over stdio (true for Claude Code, Cursor, Codex, opencode and most others). Atlas is fully usable from the CLI without any agent.

## Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-001 | `atlas scan <repo>...` indexes the given repos into a SQLite DB (default `./atlas.db`), recording repo name, path, HEAD commit, detected test command, and scan time. Re-scanning replaces that repo's nodes/edges. | Must |
| FR-002 | OpenAPI extractor: from `openapi.(yaml\|yml\|json)` files produce `endpoint` nodes (`METHOD /path`) and `field` nodes for 2xx response schema properties (resolving `$ref` to `components.schemas`, one level, plus `items` for arrays), with `EXPOSES` edges carrying file/line evidence. | Must |
| FR-003 | Python route extractor: decorators `@app.get/post/put/patch/delete("/p")`, `@router.<m>(...)`, `@app.route("/p", methods=[...])` produce `endpoint` nodes; dict-literal `return {...}` / `return jsonify({...})` keys in that function produce `field` nodes + `EXPOSES` edges. | Must |
| FR-004 | Python consumer extractor: `requests/httpx.<method>(url)` and `urlopen(url)` calls produce `http_call` nodes with method + normalized path (`/users/{}`); `x["f"]`, `x.get("f")`, `x.f` produce `field_ref` nodes (attribute access only when name is in the set of known field names). | Must |
| FR-005 | Linker: `CALLS` edges match http_call → endpoint by method and path pattern (`{param}` ≙ one path segment). `CONSUMES` edges link field_ref → field by name; confidence `exact` if the same file has a `CALLS` edge to an endpoint that `EXPOSES` that field, else `inferred`. Every edge stores evidence. | Must |
| FR-006 | `atlas impact <symbol>`: list producers exposing `<symbol>` and all consumers (repo, file, line, snippet, confidence, via endpoint). Exit code 0; `--json` prints JSON. | Must |
| FR-007 | `atlas verify <symbol> [--renamed-to <new>] [--run-tests] [--timeout N]`: per consumer repo compute `contract` ∈ {pass, fail, n/a}, `tests` ∈ {pass, fail, not_run, unknown}, and final `state` ∈ {pass, fail, not_run, unknown} with a one-line `reason`, per the rules in `02-architecture.md §6`. | Must |
| FR-008 | Test runner: detect `python -m pytest -q` when `pytest.ini`, `pyproject.toml` containing `pytest`, `setup.cfg` with `[tool:pytest]`, or a `tests/` dir exists; `.atlas.yaml` `test_cmd:` overrides; run with `subprocess.run(shell=True, cwd=repo, timeout=N)`; capture exit code and last 30 lines; never raise on failure. | Must |
| FR-009 | `atlas status`: repos indexed, node/edge counts by kind, last scan time, DB path. | Must |
| FR-010 | `atlas search <text>`: case-insensitive substring match on node names; prints kind, repo, file:line. | Should |
| FR-011 | `atlas explain-edge <id>`: print one edge with both endpoints and full evidence. | Should |
| FR-012 | `atlas serve`: MCP stdio server exposing `atlas_status`, `atlas_impact`, `atlas_verify`, `atlas_search`, `atlas_explain_edge`, all returning structured JSON (dicts). DB path from `--db` or env `ATLAS_DB`. | Must |
| FR-013 | Agent integration documented and verified with at least one real MCP client: a committed `.mcp.json` (Claude Code format) and `opencode.json` (opencode format) in the repo, plus a scripted MCP client check (`scripts/mcp_check.py`) that lists tools and calls `atlas_status`. | Must |
| FR-014 | Example workspace under `examples/` reproduces the demo end to end with a scripted sequence (`examples/demo.sh`). | Must |
| FR-015 | `atlas explain <symbol>` (optional): sends the verify table to an OpenAI-compatible open model and prints prose; never alters states; disabled unless `ATLAS_MODEL_API_KEY` is set. | Could |

## Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-001 | **Portability:** Python ≥ 3.11, macOS/Linux. Dependencies: `pyyaml`, `mcp>=2,<3` only. Dev: `pytest`. |
| NFR-002 | **Performance (estimate):** scanning 4 example repos < 2 s; a 20k-line Python repo < 30 s. Skip `.git`, `node_modules`, `.venv`, `venv`, `dist`, `build`, `__pycache__`. |
| NFR-003 | **Reliability:** an unparsable file is logged and skipped, never aborts a scan. Test runs are bounded by timeout and output limits. |
| NFR-004 | **Security:** Atlas reads files only under the given repo roots; it executes only the user's detected/declared test command; no network calls unless `atlas explain` is used; no secrets stored. |
| NFR-005 | **Privacy:** everything stays local; the DB contains file paths and short snippets of the user's code. |
| NFR-006 | **Honesty:** no state may be `pass` unless a check actually ran and succeeded; inferred-only links can never yield `pass` or `fail`. |
| NFR-007 | **Maintainability:** each module < ~250 lines; pure functions for extractors/linker; SQLite access in one module. |
| NFR-008 | **Installability:** `pipx install .` or `uv tool install .` from a clean clone works; `atlas --help` runs; documented in README. |
| NFR-009 | **Observability:** `-v` prints per-file extractor counts and skipped files to stderr; MCP server logs to stderr only (stdout is the protocol channel). |
| NFR-010 | **Cost:** $0 to run; optional explain step ≈ 1–2k tokens per call on a cheap open model. |

## Acceptance criteria (MVP done when all true)
1. `examples/demo.sh` runs from a clean clone and prints the impact list and the verify table with states `fail`, `pass`, `unknown` for billing, web, analytics respectively (and `not_run` when `--run-tests` is omitted).
2. `pytest` passes with ≥ 25 tests, none requiring network or a model.
3. From at least one real coding agent, the agent calls `atlas_impact` and `atlas_verify` over MCP and quotes their results (screenshot captured); `scripts/mcp_check.py` passes.
4. README explains install, use, agent/MCP setup, how states are decided, limitations, prior art, and license (MIT).
5. Public GitHub repo, demo video (1–3 min), X post tagging @prasad_pilla and @tryAlanAI.

## What makes it different (say this in README and video)
- Cross-repo **with evidence on every edge** — you can click to the line.
- **Four honest states** instead of a green check.
- **Agent-first via MCP**, ready for any coding agent in two minutes.
- **Small enough to read in an afternoon** — a foundation others can extend (language extractors are ~150-line pure functions).
