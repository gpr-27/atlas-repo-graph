# 05 — Full roadmap (after the MVP)

Everything here is **out of the MVP**. Each item says what it adds, how it fits the MVP design
(no rewrites), and roughly how big it is. Ordered by value ÷ effort. Open these as GitHub issues
labelled `good first issue` / `help wanted` after submission; that is how the project grows.

## Phase 1 — Make the graph broader (same architecture)

| # | Item | Design note | Size |
|---|---|---|---|
| R1 | **TypeScript/JavaScript extractors** (Express/Fastify/Next routes; `fetch`/`axios` calls; `obj.field` / destructuring refs) | New files `extract/tsroutes.py`, `extract/tsconsumers.py` using **tree-sitter** (`tree-sitter`, `tree-sitter-typescript`) as an optional extra `atlas-repo-graph[ts]`. Same `ExtractResult` contract. | L |
| R2 | **Pydantic / dataclass response models** | In `pyroutes.py`: `response_model=Model` keyword or `-> Model` annotation → resolve class fields from the same repo's `ClassDef`. | M |
| R3 | **Router prefixes** (`APIRouter(prefix="/api")`, `include_router(prefix=)`, Flask Blueprints) | Pre-pass in `pyroutes.py` collecting prefixes per router variable; prepend to paths. | M |
| R4 | **Request fields** (what consumers *send*: JSON bodies, query params) | New node kind `req_field`, edge `SENDS`; linker rule mirrors CONSUMES. | M |
| R5 | **Incremental scans** | `files(repo_id, path, sha256, mtime)` table; skip unchanged files; re-link always. | M |
| R6 | **Known field name heuristics for `.attr` access** when no producer declares the field | Keep `inferred`; add `reason="attribute name matches field"`. | S |
| R7 | **gRPC / GraphQL / events** (`.proto` services, GraphQL SDL, Kafka/SQS topic strings) | New extractors; new node kinds `rpc`, `topic`; edges `PUBLISHES`/`SUBSCRIBES`. | L |
| R8 | **Database schema links** (SQLAlchemy models ↔ migrations ↔ raw SQL strings) | Node kind `table`, `column`; edges `READS`/`WRITES`. | L |

## Phase 2 — Make verification stronger

| # | Item | Design note | Size |
|---|---|---|---|
| V1 | **Diff-aware verify** (`atlas verify --diff HEAD~1` or `--diff main`) | Parse `git diff` for changed field names in producer repos; run verify for each. Output grouped by symbol. | M |
| V2 | **Test selection** (run only tests that import the consuming module) | Map field_ref file → test files that import it (ast import graph within the repo); `test_cmd` template `python -m pytest -q {files}`. | M |
| V3 | **Contract checks beyond rename:** type change, nullability, removed endpoint, method mismatch | Store field type in `meta`; rules table like repowise's `breaking_change.py` (design only; it is AGPL). | M |
| V4 | **Snapshot diff** (`atlas scan --tag before` / `--tag after`, `atlas diff before after`) | Add `scans` table; nodes/edges carry `scan_id`; queries default to latest. Removes the need for `--renamed-to`. | M |
| V5 | **CI gate** (`atlas verify --fail-on fail,unknown`) and a GitHub Action | Exit-code policy flag; a reusable workflow in `.github/`. | S |
| V6 | **Sandboxed test runs** (Docker optional) | `--backend docker` running `test_cmd` in a container with the repo mounted read-only + tmpfs. Keep `local` default. | L |

## Phase 3 — Make it nicer to use

| # | Item | Design note | Size |
|---|---|---|---|
| U1 | **`atlas graph --html`** single-file SVG map of repos and edges (Stretch B) | No JS deps; boxes per repo, arrows per CALLS/CONSUMES, tooltips with evidence. | M |
| U2 | **`atlas explain`** with an open model (Stretch A) | `explain.py`, OpenAI-compatible endpoint; prose only, never states. | S |
| U3 | **Workspace file** `atlas.yaml` listing repos, test commands, ignore globs | `atlas scan` with no args reads it. | S |
| U4 | **MCP resources** (`atlas://repos`, `atlas://edges/{id}`) and prompts (`atlas/impact-before-edit`) | Using `@mcp.resource` / `@mcp.prompt`. | S |
| U5 | **Rich terminal output** behind an optional extra | Keep plain tables as default. | S |
| U6 | **Homebrew / PyPI release** `pipx install atlas-repo-graph` | Tag `v0.1.0`, `python -m build`, publish. | S |

## Phase 4 — Scale and trust

| # | Item | Design note | Size |
|---|---|---|---|
| S1 | **Confidence scores** (0–1) alongside `exact`/`inferred`, per origin (OpenAPI 0.9, AST route 0.85, client call 0.75, name match 0.65) | Add `score REAL` to edges; keep the two-level label as the user-facing truth. | S |
| S2 | **Unresolved table** (calls/refs that matched nothing, with reason) | `unresolved(repo_id, kind, name, file, line, reason)`; show in `status`. | S |
| S3 | **Large-repo performance** (parallel extraction with `concurrent.futures`, batched inserts) | Extractors are pure, so this is safe. | M |
| S4 | **Security hardening**: refuse `test_cmd` from `.atlas.yaml` unless `--trust-repo-config`; redact secrets from snippets (`AKIA…`, `sk-…`) | Flag + regex scrub in `read_snippet`. | S |
| S5 | **Plugin API for extractors** (`atlas.extractors` entry points) | Discover via `importlib.metadata.entry_points`. | M |

## Explicitly never (keep the project honest and small)
- No hosted service, accounts, or telemetry.
- No model in the decision path for links or states.
- No automatic code modification.
