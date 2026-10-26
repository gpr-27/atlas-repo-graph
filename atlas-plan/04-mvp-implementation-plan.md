# Atlas MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `atlas-repo-graph` v0.1.0: a CLI + MCP server that scans several local Python/OpenAPI repos, links producers to consumers with evidence, answers `impact`, and reports `verify` with four honest states.

**Architecture:** Pure-function extractors (`ast`, YAML/JSON) → a linker → one SQLite file → query/verify modules → thin CLI and MCP adapters. No model in the decision path. See `02-architecture.md` for every name used below.

**Tech Stack:** Python ≥ 3.11, stdlib (`ast`, `sqlite3`, `argparse`, `subprocess`, `re`, `json`), `pyyaml>=6`, `mcp>=2,<3`, `pytest`.

**Spec:** `01-product-spec.md` (requirements) and `02-architecture.md` (contracts). Read both before Task 0.

## Global Constraints

- Python ≥ 3.11. Runtime deps **only** `pyyaml>=6` and `mcp>=2,<3`. Dev dep `pytest>=8`. No other packages without a written reason.
- Package dir `atlas/`, distribution name `atlas-repo-graph`, CLI entry `atlas = "atlas.cli:main"`, `__version__ = "0.1.0"`.
- All names, signatures, table columns, node/edge kinds, states and rules come from `02-architecture.md` §3–§11. Do not rename.
- Every edge stores evidence (`ev_file`, `ev_line`, `ev_snippet`, `extractor`, `reason`). Snippet = source line stripped, ≤ 200 chars.
- `state == "pass"` only when tests actually ran and passed **and** confidence is `exact` (NFR-006).
- Extractors never raise on bad input; they append `"file: reason"` to `ExtractResult.skipped`.
- `mcp_server.py` never writes to stdout except through the MCP transport.
- Skip dirs: `.git .hg .svn node_modules .venv venv env dist build __pycache__ .mypy_cache .pytest_cache site-packages`.
- Tests must run offline with no model and no network. Command: `python -m pytest -q`.
- Commit after every task with the message given in the task. No `Co-Authored-By` lines.
- Work in a venv: `uv venv .venv && source .venv/bin/activate && uv pip install -e ".[dev]"` (or `python -m venv` + `pip`).

## Review Focus

Inputs the spec implies that no single task's happy path covers. Each gets a test in the task named.
1. **A repo with a syntax error in one `.py` file** → scan still completes; file listed in skipped; counts for other files unchanged. (Task 4, Task 6)
2. **An http_call whose path never matches any endpoint** (e.g. `GET /nope`) → node is stored, no CALLS edge, `search nope` finds it, `impact` ignores it. (Task 5, Task 7)
3. **A field name that exists in two different producers** (e.g. `id` in two endpoints) → `impact id` lists both producers; CONSUMES edges are exact only toward the endpoint the file actually calls. (Task 5)
4. **`verify` on a symbol nobody references** → empty table, exit 0, message "no consumers reference `x`". (Task 8)
5. **Test command hangs** → `tests == "unknown"` with reason "timed out after N s", other repos still verified. (Task 8)

---

### Task 0: Repository skeleton and tooling

**Files:**
- Create: `pyproject.toml`, `atlas/__init__.py`, `atlas/extract/__init__.py`, `tests/__init__.py`, `tests/test_models.py`, `.gitignore`, `LICENSE` (MIT, year 2026, your name), `README.md` (title + one paragraph; full README in Task 11)

**Interfaces:**
- Produces: importable package `atlas` with `atlas.__version__ == "0.1.0"`; `pytest` runs.

- [ ] **Step 1: Create the project**

```bash
mkdir atlas-repo-graph && cd atlas-repo-graph && git init -b main
uv venv .venv && source .venv/bin/activate
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "atlas-repo-graph"
version = "0.1.0"
description = "Cross-repo impact map with evidence on every edge and honest pass/fail/not_run/unknown states."
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
dependencies = ["pyyaml>=6", "mcp>=2,<3"]

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
atlas = "atlas.cli:main"

[tool.setuptools.packages.find]
include = ["atlas*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Write `atlas/__init__.py`** containing `__version__ = "0.1.0"`, and empty `atlas/extract/__init__.py`, `tests/__init__.py`.

- [ ] **Step 4: Write the failing test** `tests/test_models.py`:

```python
def test_version():
    import atlas
    assert atlas.__version__ == "0.1.0"
```

- [ ] **Step 5: Install and run**

Run: `uv pip install -e ".[dev]" && python -m pytest -q`
Expected: `1 passed`

- [ ] **Step 6: `.gitignore`**: `.venv/ __pycache__/ *.pyc *.egg-info/ dist/ build/ atlas.db *.db .pytest_cache/ examples/**/atlas.db`

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "chore: project skeleton for atlas-repo-graph"
```

---

### Task 1: Models and SQLite store

**Files:**
- Create: `atlas/models.py`, `atlas/db.py`
- Test: `tests/test_models.py` (extend), `tests/test_db.py`

**Interfaces:**
- Produces (`atlas/models.py`): exactly the dataclasses and constants in `02-architecture.md` §4 (`Node`, `Evidence`, `Edge`, `ExtractResult`, `RepoInfo`, `ImpactRow`, `ImpactResult`, `VerifyRow`, `NODE_KINDS`, `EDGE_KINDS`, `CONFIDENCES`, `STATES`, `HTTP_METHODS`).
- Produces (`atlas/db.py`):
  - `open_db(path: str | Path) -> sqlite3.Connection` — sets `row_factory = sqlite3.Row`, `PRAGMA foreign_keys=ON`, calls `init_schema`.
  - `init_schema(conn) -> None` — DDL from §3, idempotent, sets `PRAGMA user_version=1`.
  - `replace_repo(conn, repo: RepoInfo, nodes: list[Node], edges: list[Edge], snippets: dict[str, str]) -> dict[str, int]` — deletes existing repo row by name (cascade), inserts repo, nodes, then edges whose **both** endpoints exist (`src_key`/`dst_key` → ids via a key→id map built from *all* nodes in DB, so cross-repo edges work). Returns `{"nodes": n, "edges": m}`.
  - `replace_cross_edges(conn, edges: list[Edge]) -> int` — deletes all edges with `kind IN ('CALLS','CONSUMES')`, inserts the given ones (used by scan after linking). Returns count.
  - `node_id_by_key(conn, key: str) -> int | None`
  - `fetch_nodes(conn, kind: str | None = None, name: str | None = None) -> list[sqlite3.Row]`
  - `fetch_edges(conn, kind: str | None = None, dst_id: int | None = None, src_id: int | None = None) -> list[sqlite3.Row]`
  - `fetch_repos(conn) -> list[sqlite3.Row]`

- [ ] **Step 1: Write failing tests** `tests/test_db.py`:

```python
from atlas.db import open_db, replace_repo, fetch_nodes, fetch_edges, fetch_repos, replace_cross_edges
from atlas.models import Node, Edge, Evidence, RepoInfo

def _ev(): return Evidence(file="app.py", line=3, snippet='return {"customer_id": 1}', extractor="pyroutes", reason="dict literal in return")

def test_schema_is_idempotent(tmp_path):
    conn = open_db(tmp_path / "a.db"); conn.close()
    conn = open_db(tmp_path / "a.db")
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1

def test_replace_repo_inserts_and_replaces(tmp_path):
    conn = open_db(tmp_path / "a.db")
    ep = Node("backend", "endpoint", "GET /users/{user_id}", "app.py", 2, {"method": "GET", "path": "/users/{user_id}", "pattern": "^/users/[^/]+$"})
    f = Node("backend", "field", "customer_id", "app.py", 3, {"endpoint": ep.name})
    e = Edge(ep.key, f.key, "EXPOSES", "exact", _ev())
    counts = replace_repo(conn, RepoInfo("backend", "/x/backend", "abc", None), [ep, f], [e], {ep.key: "@app.get", f.key: "return {"})
    assert counts == {"nodes": 2, "edges": 1}
    counts = replace_repo(conn, RepoInfo("backend", "/x/backend", "abc", None), [ep], [], {})
    assert counts == {"nodes": 1, "edges": 0}
    assert len(fetch_nodes(conn)) == 1 and len(fetch_edges(conn)) == 0
    assert fetch_repos(conn)[0]["name"] == "backend"

def test_cross_edges_link_nodes_from_different_repos(tmp_path):
    conn = open_db(tmp_path / "a.db")
    f = Node("backend", "field", "customer_id", "app.py", 3, {"endpoint": "GET /users/{user_id}"})
    r = Node("billing", "field_ref", "customer_id", "charge.py", 9, {"access": "subscript", "function": "charge"})
    replace_repo(conn, RepoInfo("backend", "/x/backend", None, None), [f], [], {})
    replace_repo(conn, RepoInfo("billing", "/x/billing", None, "python -m pytest -q"), [r], [], {})
    n = replace_cross_edges(conn, [Edge(r.key, f.key, "CONSUMES", "inferred", Evidence("charge.py", 9, 'data["customer_id"]', "link", "name match only"))])
    assert n == 1
    row = fetch_edges(conn, kind="CONSUMES")[0]
    assert row["confidence"] == "inferred" and row["ev_snippet"] == 'data["customer_id"]'
```

- [ ] **Step 2: Run to verify they fail** — `python -m pytest tests/test_db.py -q` → ImportError.

- [ ] **Step 3: Implement `atlas/models.py`** exactly as §4 (copy the block). Add `def as_dict(obj) -> dict` helper = `dataclasses.asdict`.

- [ ] **Step 4: Implement `atlas/db.py`** per the interface. `meta` stored as `node.meta_json` (sorted keys). Insert nodes with `INSERT OR IGNORE`, then build `key -> id` map by selecting all nodes joined to repos (key = `f"{repo}|{kind}|{name}|{file}|{line}|{meta}"`, identical to `Node.key`). Edges whose keys are missing are skipped silently (return count reflects inserted).

- [ ] **Step 5: Run tests** — `python -m pytest -q` → all pass.

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: models and sqlite store"`

---

### Task 2: OpenAPI extractor

**Files:**
- Create: `atlas/extract/openapi.py`, `tests/fixtures/openapi_repo/openapi.yaml`, `tests/test_openapi.py`

**Interfaces:**
- Produces: `extract_openapi(repo_name: str, repo_root: Path) -> ExtractResult` (§5.2). Also `find_openapi_files(repo_root: Path) -> list[Path]` and `path_pattern(path: str) -> str` (shared with Task 3; lives in `atlas/extract/__init__.py`).
- `path_pattern("/users/{user_id}") == "^/users/[^/]+$"`; also converts `:id` and `<int:id>` segments to `[^/]+`; escapes other regex characters with `re.escape` per literal segment.

- [ ] **Step 1: Fixture** `tests/fixtures/openapi_repo/openapi.yaml`:

```yaml
openapi: 3.0.3
info: { title: Users, version: "1" }
paths:
  /users/{user_id}:
    get:
      responses:
        "200":
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/User"
  /users:
    get:
      responses:
        "200":
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: "#/components/schemas/User"
components:
  schemas:
    User:
      type: object
      properties:
        id: { type: integer }
        customer_id: { type: string }
        email: { type: string }
```

- [ ] **Step 2: Failing tests** `tests/test_openapi.py`:

```python
from pathlib import Path
from atlas.extract import path_pattern
from atlas.extract.openapi import extract_openapi

FIX = Path(__file__).parent / "fixtures" / "openapi_repo"

def test_path_pattern():
    assert path_pattern("/users/{user_id}") == "^/users/[^/]+$"
    assert path_pattern("/a/:id/b") == "^/a/[^/]+/b$"
    assert path_pattern("/a/<int:id>") == "^/a/[^/]+$"
    assert path_pattern("/users") == "^/users$"

def test_extract_endpoints_and_fields():
    r = extract_openapi("backend", FIX)
    names = sorted(n.name for n in r.nodes if n.kind == "endpoint")
    assert names == ["GET /users", "GET /users/{user_id}"]
    fields = sorted((n.meta["endpoint"], n.name) for n in r.nodes if n.kind == "field")
    assert ("GET /users/{user_id}", "customer_id") in fields
    assert ("GET /users", "customer_id") in fields            # array items resolved
    assert len([e for e in r.edges if e.kind == "EXPOSES"]) == 6
    ep = next(n for n in r.nodes if n.name == "GET /users/{user_id}")
    assert ep.file == "openapi.yaml" and ep.line == 4 and ep.meta["pattern"] == "^/users/[^/]+$"
    assert all(e.evidence.extractor == "openapi" and e.evidence.snippet for e in r.edges)

def test_bad_yaml_is_skipped(tmp_path):
    (tmp_path / "openapi.yaml").write_text("paths: [unclosed")
    r = extract_openapi("x", tmp_path)
    assert r.nodes == [] and r.skipped and "openapi.yaml" in r.skipped[0]
```

- [ ] **Step 3: Run** → fails (ImportError).

- [ ] **Step 4: Implement** `atlas/extract/__init__.py` (`path_pattern`, `SKIP_DIRS`, `iter_files(repo_root, suffixes) -> Iterator[Path]` that honours `SKIP_DIRS`) and `atlas/extract/openapi.py` per §5.2. Line numbers: scan raw text lines for the first line whose stripped form starts with the quoted-or-bare path key followed by `:`; for properties, first line after the schema's `properties:` whose stripped form starts with `<name>:`; fallback to the endpoint line. Snippet = that raw line stripped.

- [ ] **Step 5: Run** → pass. **Step 6: Commit** — `git add -A && git commit -m "feat: openapi extractor"`

---

### Task 3: Python route extractor

**Files:**
- Create: `atlas/extract/pyroutes.py`, `tests/fixtures/routes_repo/app.py`, `tests/test_pyroutes.py`

**Interfaces:**
- Produces: `extract_py_routes(repo_name: str, repo_root: Path) -> ExtractResult` (§5.3). Helper `parse_file(path: Path) -> ast.Module | None` in `atlas/extract/__init__.py` (returns None and lets the caller record skipped on `SyntaxError`/`UnicodeDecodeError`).

- [ ] **Step 1: Fixture** `tests/fixtures/routes_repo/app.py`:

```python
from fastapi import FastAPI, APIRouter
from flask import jsonify
app = FastAPI()
router = APIRouter()

@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {"id": user_id, "customer_id": f"C{user_id}", "email": "a@b.c"}

@router.post("/orders")
def create_order():
    return jsonify({"order_id": 1})

@app.route("/legacy/<int:id>", methods=["GET", "DELETE"])
def legacy(id):
    return {"ok": True}

@app.get("/opaque")
def opaque():
    user = load()
    return user
```

- [ ] **Step 2: Failing tests** `tests/test_pyroutes.py`:

```python
from pathlib import Path
from atlas.extract.pyroutes import extract_py_routes
FIX = Path(__file__).parent / "fixtures" / "routes_repo"

def test_routes_and_fields():
    r = extract_py_routes("backend", FIX)
    eps = {n.name: n for n in r.nodes if n.kind == "endpoint"}
    assert set(eps) == {"GET /users/{user_id}", "POST /orders", "GET /legacy/<int:id>", "DELETE /legacy/<int:id>", "GET /opaque"}
    assert eps["GET /users/{user_id}"].line == 6 and eps["GET /users/{user_id}"].meta["pattern"] == "^/users/[^/]+$"
    fields = {(n.meta["endpoint"], n.name): n for n in r.nodes if n.kind == "field"}
    assert ("GET /users/{user_id}", "customer_id") in fields
    assert fields[("GET /users/{user_id}", "customer_id")].line == 8
    assert ("POST /orders", "order_id") in fields
    assert ("GET /legacy/<int:id>", "ok") in fields and ("DELETE /legacy/<int:id>", "ok") in fields
    assert not any(k[0] == "GET /opaque" for k in fields)
    assert any("app.py:18" in s and "non-literal return" in s for s in r.skipped)
    edge = next(e for e in r.edges if e.dst_key == fields[("GET /users/{user_id}", "customer_id")].key)
    assert edge.kind == "EXPOSES" and edge.confidence == "exact" and edge.evidence.extractor == "pyroutes"
    assert "customer_id" in edge.evidence.snippet

def test_syntax_error_file_is_skipped(tmp_path):
    (tmp_path / "bad.py").write_text("def (:\n")
    r = extract_py_routes("x", tmp_path)
    assert r.nodes == [] and any("bad.py" in s for s in r.skipped)
```

- [ ] **Step 3: Run** → fails. **Step 4: Implement** per §5.3 using `ast.walk` for functions, decorator matching, and a nested walk for `Return` nodes inside the function body (do not descend into nested `FunctionDef`). Line of a field = the key `Constant` node's `lineno`. Snippet = that source line stripped.

- [ ] **Step 5: Run** → pass. **Step 6: Commit** — `git add -A && git commit -m "feat: python route extractor"`

---

### Task 4: Python consumer extractor

**Files:**
- Create: `atlas/extract/pyconsumers.py`, `tests/fixtures/consumer_repo/charge.py`, `tests/fixtures/consumer_repo/report.py`, `tests/test_pyconsumers.py`

**Interfaces:**
- Produces: `extract_py_consumers(repo_name: str, repo_root: Path, known_fields: set[str]) -> ExtractResult` (§5.4). Helper `url_to_path(node: ast.expr) -> str | None` (the normalization rules) exported for tests.

- [ ] **Step 1: Fixtures**

`tests/fixtures/consumer_repo/charge.py`:
```python
import requests
BASE = "http://localhost:8000"

def charge_user(user_id, amount):
    resp = requests.get(f"{BASE}/users/{user_id}")
    data = resp.json()
    name = data.get("email")
    return {"customer": data["customer_id"], "amount": amount, "email": name}

def ping():
    return requests.get("http://localhost:8000/health/").status_code
```

`tests/fixtures/consumer_repo/report.py`:
```python
import csv
def totals(path):
    with open(path) as f:
        for row in csv.DictReader(f):
            yield row["customer_id"], row.customer_id
```

- [ ] **Step 2: Failing tests** `tests/test_pyconsumers.py`:

```python
import ast
from pathlib import Path
from atlas.extract.pyconsumers import extract_py_consumers, url_to_path
FIX = Path(__file__).parent / "fixtures" / "consumer_repo"

def _expr(src): return ast.parse(src).body[0].value

def test_url_to_path():
    assert url_to_path(_expr('"http://h:1/users/5"')) == "/users/5"
    assert url_to_path(_expr('f"{BASE}/users/{uid}"')) == "/users/{}"
    assert url_to_path(_expr('BASE + "/users/" + str(uid)')) == "/users/{}"
    assert url_to_path(_expr('"http://h/health/"')) == "/health"
    assert url_to_path(_expr('make_url()')) is None

def test_http_calls_and_field_refs():
    r = extract_py_consumers("billing", FIX, known_fields={"customer_id", "email"})
    calls = {n.name: n for n in r.nodes if n.kind == "http_call"}
    assert set(calls) == {"GET /users/{}", "GET /health"}
    assert calls["GET /users/{}"].file == "charge.py" and calls["GET /users/{}"].line == 5
    assert calls["GET /users/{}"].meta == {"method": "GET", "path": "/users/{}", "library": "requests"}
    refs = sorted((n.file, n.line, n.name, n.meta["access"], n.meta["function"]) for n in r.nodes if n.kind == "field_ref")
    assert ("charge.py", 7, "email", "get", "charge_user") in refs
    assert ("charge.py", 8, "customer_id", "subscript", "charge_user") in refs
    assert ("report.py", 5, "customer_id", "subscript", "totals") in refs
    assert ("report.py", 5, "customer_id", "attr", "totals") in refs
    assert not any(n.name == "status_code" for n in r.nodes)   # attr not in known_fields

def test_requests_get_is_not_a_field_ref():
    r = extract_py_consumers("billing", FIX, known_fields=set())
    assert not any(n.kind == "field_ref" and n.name.startswith("http") for n in r.nodes)
```

- [ ] **Step 3: Run** → fails. **Step 4: Implement** per §5.4. Track the enclosing function with a small `ast.NodeVisitor` that pushes/pops on `FunctionDef`/`AsyncFunctionDef`. For `.get("x")` refs, exclude when the receiver is a `Name`/`Attribute` whose root id is in `{"requests","httpx","client","session"}`. Also exclude `Subscript` whose slice is not a string `Constant`.

- [ ] **Step 5: Run** → pass. **Step 6: Commit** — `git add -A && git commit -m "feat: python consumer extractor"`

---

### Task 5: Linker

**Files:**
- Create: `atlas/link.py`, `tests/test_link.py`

**Interfaces:**
- Produces: `link(nodes: list[Node], snippets: dict[str, str]) -> list[Edge]` (§5.5).

- [ ] **Step 1: Failing tests** `tests/test_link.py` (build nodes by hand; no files):

```python
from atlas.link import link
from atlas.models import Node

def _n(repo, kind, name, file, line, **meta): return Node(repo, kind, name, file, line, meta)

EP = _n("backend", "endpoint", "GET /users/{user_id}", "app.py", 6, method="GET", path="/users/{user_id}", pattern="^/users/[^/]+$")
F  = _n("backend", "field", "customer_id", "app.py", 8, endpoint="GET /users/{user_id}")
EP2 = _n("backend", "endpoint", "GET /orders/{id}", "app.py", 20, method="GET", path="/orders/{id}", pattern="^/orders/[^/]+$")
F2 = _n("backend", "field", "id", "app.py", 21, endpoint="GET /orders/{id}")
F3 = _n("backend", "field", "id", "app.py", 7, endpoint="GET /users/{user_id}")
CALL = _n("billing", "http_call", "GET /users/{}", "charge.py", 5, method="GET", path="/users/{}", library="requests")
REF  = _n("billing", "field_ref", "customer_id", "charge.py", 8, access="subscript", function="charge_user")
REF_ID = _n("billing", "field_ref", "id", "charge.py", 9, access="subscript", function="charge_user")
ORPHAN_CALL = _n("billing", "http_call", "GET /nope", "charge.py", 30, method="GET", path="/nope", library="requests")
AN_REF = _n("analytics", "field_ref", "customer_id", "report.py", 5, access="subscript", function="totals")
SNIP = {CALL.key: 'resp = requests.get(f"{BASE}/users/{user_id}")', REF.key: 'data["customer_id"]', REF_ID.key: 'data["id"]', AN_REF.key: 'row["customer_id"]', ORPHAN_CALL.key: 'requests.get("/nope")'}

def test_calls_edge_matches_method_and_pattern():
    edges = link([EP, F, CALL], SNIP)
    e = [x for x in edges if x.kind == "CALLS"]
    assert len(e) == 1 and e[0].src_key == CALL.key and e[0].dst_key == EP.key and e[0].confidence == "exact"
    assert e[0].evidence.file == "charge.py" and e[0].evidence.line == 5 and "requests.get" in e[0].evidence.snippet

def test_consumes_exact_when_same_file_calls_endpoint():
    edges = link([EP, F, CALL, REF], SNIP)
    c = [x for x in edges if x.kind == "CONSUMES"]
    assert len(c) == 1 and c[0].confidence == "exact" and c[0].evidence.reason == "same file calls GET /users/{user_id}"

def test_consumes_inferred_without_call():
    edges = link([EP, F, AN_REF], SNIP)
    c = [x for x in edges if x.kind == "CONSUMES"]
    assert len(c) == 1 and c[0].confidence == "inferred" and c[0].evidence.reason == "name match only"

def test_same_field_name_in_two_endpoints_is_exact_only_toward_called_one():
    edges = link([EP, EP2, F2, F3, CALL, REF_ID], SNIP)
    c = {x.dst_key: x.confidence for x in edges if x.kind == "CONSUMES"}
    assert c[F3.key] == "exact" and c[F2.key] == "inferred"

def test_orphan_call_gets_no_edge_and_no_error():
    assert [x for x in link([EP, ORPHAN_CALL], SNIP) if x.kind == "CALLS"] == []

def test_no_edges_within_same_repo():
    same = _n("backend", "field_ref", "customer_id", "app.py", 40, access="subscript", function="x")
    assert link([EP, F, same], {same.key: "x"}) == []
```

- [ ] **Step 2: Run** → fails. **Step 3: Implement** `atlas/link.py` per §5.5. Use `re.fullmatch(pattern, path.replace("{}", "x"))`. Build an index `endpoint name -> Node` and `field name -> [Node]` first; O(n·m) is fine.

- [ ] **Step 4: Run** → pass. **Step 5: Commit** — `git add -A && git commit -m "feat: cross-repo linker"`

---

### Task 6: Scan orchestration, `status`, and the CLI shell

**Files:**
- Create: `atlas/scan.py`, `atlas/render.py` (only `render_table`, `render_status` for now), `atlas/cli.py`, `tests/test_scan.py`, `tests/test_cli.py`
- Test fixtures: reuse `tests/fixtures/openapi_repo`, `routes_repo`, `consumer_repo` as three "repos".

**Interfaces:**
- Produces:
  - `scan_repos(paths: list[Path], db_path: Path, verbose: bool = False) -> dict` returning `{"repos": [{"name", "nodes", "edges", "skipped": [...]}], "cross_edges": n}`.
  - `detect_test_cmd(repo_root: Path) -> str | None` and `git_head(repo_root: Path) -> str | None` in `scan.py`.
  - `read_snippet(repo_root: Path, file: str, line: int) -> str` in `scan.py` (cached per file; returns "" if unreadable).
  - `status(conn) -> dict` in `atlas/query.py` (create the module now with just this function; Task 7 adds the rest).
  - `render_table(headers, rows) -> str`, `render_status(s) -> str` in `render.py`.
  - `main(argv: list[str] | None = None) -> int` in `cli.py` with subcommands `scan`, `status` (others added later). `--db` default from `ATLAS_DB` env else `./atlas.db`.

- [ ] **Step 1: Failing tests** `tests/test_scan.py`:

```python
from pathlib import Path
from atlas.scan import scan_repos, detect_test_cmd
from atlas.db import open_db, fetch_edges, fetch_repos
from atlas.query import status
FIX = Path(__file__).parent / "fixtures"

def test_detect_test_cmd(tmp_path):
    assert detect_test_cmd(tmp_path) is None
    (tmp_path / "tests").mkdir()
    assert detect_test_cmd(tmp_path) == "python -m pytest -q"
    (tmp_path / ".atlas.yaml").write_text("test_cmd: make test\n")
    assert detect_test_cmd(tmp_path) == "make test"

def test_scan_three_repos_links_across(tmp_path):
    db = tmp_path / "atlas.db"
    s = scan_repos([FIX / "openapi_repo", FIX / "routes_repo", FIX / "consumer_repo"], db)
    assert [r["name"] for r in s["repos"]] == ["openapi_repo", "routes_repo", "consumer_repo"]
    assert s["cross_edges"] >= 3
    conn = open_db(db)
    kinds = {k: 0 for k in ("CALLS", "CONSUMES")}
    for e in fetch_edges(conn):
        if e["kind"] in kinds: kinds[e["kind"]] += 1
    assert kinds["CALLS"] >= 1 and kinds["CONSUMES"] >= 2
    st = status(conn)
    assert st["nodes"]["endpoint"] >= 5 and st["edges"]["EXPOSES"] >= 6 and len(st["repos"]) == 3

def test_scan_is_idempotent(tmp_path):
    db = tmp_path / "atlas.db"
    a = scan_repos([FIX / "routes_repo", FIX / "consumer_repo"], db)
    b = scan_repos([FIX / "routes_repo", FIX / "consumer_repo"], db)
    assert a == b
```

and `tests/test_cli.py`:

```python
from pathlib import Path
from atlas.cli import main
FIX = Path(__file__).parent / "fixtures"

def test_scan_and_status(tmp_path, capsys):
    db = str(tmp_path / "a.db")
    assert main(["scan", str(FIX / "routes_repo"), str(FIX / "consumer_repo"), "--db", db]) == 0
    assert main(["status", "--db", db]) == 0
    out = capsys.readouterr().out
    assert "routes_repo" in out and "consumer_repo" in out and "endpoint" in out

def test_status_missing_db_returns_1(tmp_path, capsys):
    assert main(["status", "--db", str(tmp_path / "none.db")]) == 1
    assert "not found" in capsys.readouterr().err.lower()
```

- [ ] **Step 2: Run** → fails. **Step 3: Implement**
  - `scan_repos`: resolve names (basename, dedupe with `-2`), for each repo: `RepoInfo(name, str(path.resolve()), git_head, detect_test_cmd)`; run `extract_openapi` + `extract_py_routes`; collect `known_fields` from all producer field names across **all** repos (two passes: producers for all repos first, then consumers); build `snippets` via `read_snippet` for every node; `replace_repo` per repo (in-repo EXPOSES edges only); then `link(all_nodes, snippets)` → `replace_cross_edges`. `verbose` prints per-repo counts and skipped to stderr.
  - `status`: counts via `SELECT kind, COUNT(*) ... GROUP BY kind` for nodes and edges.
  - `cli.main`: `argparse` with subparsers; `status` returns 1 with `error: database not found: <path>` on stderr if the file is missing. Catch `KeyboardInterrupt` → 130.
  - `render_table`: compute column widths, left-align, two spaces between columns, header underline with `-`.

- [ ] **Step 4: Run** `python -m pytest -q` → pass. Also run `atlas scan tests/fixtures/routes_repo tests/fixtures/consumer_repo --db /tmp/t.db -v && atlas status --db /tmp/t.db` and read the output.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: scan orchestration, status, cli shell"`

---

### Task 7: `impact`, `search`, `explain-edge`

**Files:**
- Modify: `atlas/query.py`, `atlas/render.py`, `atlas/cli.py`
- Test: `tests/test_query.py`, extend `tests/test_cli.py`

**Interfaces:**
- Produces: `impact(conn, symbol) -> ImpactResult`, `search(conn, text, limit=50) -> list[dict]`, `explain_edge(conn, edge_id) -> dict | None` (§7); `render_impact(r) -> str`; CLI `impact <symbol> [--json]`, `search <text> [--json]`, `explain-edge <id> [--json]`.

- [ ] **Step 1: Failing tests** `tests/test_query.py` (scan the three fixtures into `tmp_path` in a fixture, then):

```python
def test_impact_lists_producers_and_consumers(conn):
    r = impact(conn, "customer_id")
    assert {p["endpoint"] for p in r.producers} >= {"GET /users/{user_id}"}
    rows = {(c.repo, c.file, c.line): c for c in r.consumers}
    exact = rows[("consumer_repo", "charge.py", 8)]
    assert exact.confidence == "exact" and exact.via == "GET /users/{user_id}" and 'data["customer_id"]' in exact.snippet
    inferred = rows[("consumer_repo", "report.py", 5)]
    assert inferred.confidence == "inferred" and inferred.via == "name match"
    assert all(c.edge_id > 0 for c in r.consumers)

def test_impact_unknown_symbol_is_empty(conn):
    r = impact(conn, "nope_field")
    assert r.producers == [] and r.consumers == []

def test_search_and_explain(conn):
    hits = search(conn, "health")        # the orphan http_call "GET /health" from the consumer fixture
    assert hits and hits[0]["kind"] == "http_call"
    eid = impact(conn, "customer_id").consumers[0].edge_id
    e = explain_edge(conn, eid)
    assert e["kind"] == "CONSUMES" and e["src"]["repo"] == "consumer_repo" and e["dst"]["repo"] in ("routes_repo", "openapi_repo")
    assert e["evidence"]["snippet"] and e["evidence"]["extractor"] == "link"
    assert explain_edge(conn, 999999) is None
```

CLI additions in `tests/test_cli.py`: `impact customer_id --json` prints JSON with keys `symbol, producers, consumers`; `explain-edge 999999` returns 1 with "edge not found".

- [ ] **Step 2: Run** → fails. **Step 3: Implement** per §7 and §11. `impact` SQL: fields named symbol → their ids; CONSUMES edges with `dst_id IN (...)` joined to src node + repo. If no producers, fall back to field_ref nodes named symbol → rows with confidence `inferred`, via `name match`, `edge_id = 0`.

- [ ] **Step 4: Run** → pass. **Step 5: Commit** — `git add -A && git commit -m "feat: impact, search, explain-edge"`

---

### Task 8: `verify` — contract check, test runner, four states

**Files:**
- Create: `atlas/verify.py`, `tests/test_verify.py`, `docs/how-states-are-decided.md`
- Modify: `atlas/render.py` (`render_verify`), `atlas/cli.py` (`verify` subcommand; exit 2 on any `fail`)

**Interfaces:**
- Produces: `verify(conn, symbol, renamed_to=None, run_tests=False, timeout=120) -> list[VerifyRow]`; `run_test_cmd(cmd: str, cwd: str, timeout: int) -> tuple[str, str]` returning `(tests_state, last_30_lines)`; `decide_state(confidence, contract, tests) -> str` (pure, exported for tests).

- [ ] **Step 1: Failing tests** `tests/test_verify.py`:

```python
import pytest
from atlas.verify import decide_state, run_test_cmd, verify

@pytest.mark.parametrize("conf,contract,tests,expected", [
    ("inferred", "fail", "pass", "unknown"),
    ("inferred", "pass", "pass", "unknown"),
    ("exact", "fail", "not_run", "fail"),
    ("exact", "pass", "fail", "fail"),
    ("exact", "pass", "pass", "pass"),
    ("exact", "pass", "not_run", "not_run"),
    ("exact", "n/a", "not_run", "unknown"),
    ("exact", "pass", "unknown", "unknown"),
])
def test_decide_state(conf, contract, tests, expected):
    assert decide_state(conf, contract, tests) == expected

def test_run_test_cmd_pass_fail_timeout(tmp_path):
    assert run_test_cmd("exit 0", str(tmp_path), 5)[0] == "pass"
    state, out = run_test_cmd("echo boom; exit 3", str(tmp_path), 5)
    assert state == "fail" and "boom" in out
    state, out = run_test_cmd("sleep 5", str(tmp_path), 1)
    assert state == "unknown" and "timed out" in out

def test_verify_rows_on_fixture_workspace(ws):
    # ws: fixture that builds a 3-repo workspace in tmp_path where:
    #   producer exposes customer_id (openapi + route), consumer A refs it with a call (exact), consumer B refs it by name only (inferred)
    rows = {r.repo: r for r in verify(ws.conn, "customer_id")}
    assert rows["consumer_a"].state == "not_run" and rows["consumer_a"].contract == "pass" and rows["consumer_a"].tests == "not_run"
    assert rows["consumer_b"].state == "unknown" and rows["consumer_b"].confidence == "inferred"

def test_verify_after_rename(ws_renamed):
    # ws_renamed: producer now exposes account_id, consumer A still refs customer_id (exact call), consumer C refs account_id (exact), consumer B name-only
    rows = {r.repo: r for r in verify(ws_renamed.conn, "customer_id", renamed_to="account_id", run_tests=True, timeout=30)}
    assert rows["consumer_a"].state == "fail" and rows["consumer_a"].contract == "fail"
    assert rows["consumer_c"].state == "pass" and rows["consumer_c"].contract == "pass" and rows["consumer_c"].tests == "pass"
    assert rows["consumer_b"].state == "unknown"

def test_verify_nobody_references(ws):
    assert verify(ws.conn, "ghost") == []
```

Build `ws` / `ws_renamed` as pytest fixtures in the test file using `tmp_path`, writing these exact files, then `scan_repos([...], tmp_path/"a.db")` and returning an object with `.conn = open_db(...)`:

```
producer/app.py          ws:         @app.get("/u/{id}")\ndef g(id):\n    return {"customer_id": 1}
                         ws_renamed: same but {"account_id": 1}
                         (prefix both with the 5-line try/except FastAPI stub from Task 10)
consumer_a/a.py          from urllib.request import urlopen\nB = "http://x"\ndef f(i):\n    d = urlopen(f"{B}/u/{i}")\n    return d["customer_id"]
consumer_a/tests/test_a.py   def test_a():\n    assert False
consumer_b/b.py          def f(row):\n    return row["customer_id"]          (no tests dir)
consumer_c/c.py          (ws_renamed only) same as consumer_a but d["account_id"]
consumer_c/tests/test_c.py   def test_c():\n    assert True
```
`ws` scans producer, consumer_a, consumer_b. `ws_renamed` scans producer, consumer_a, consumer_b, consumer_c.

- [ ] **Step 2: Run** → fails. **Step 3: Implement** per §6 exactly. `run_test_cmd`: if `cmd` starts with `"python "`, replace that first token with `sys.executable` (§6.9); then `subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)`; on `TimeoutExpired` return `("unknown", f"timed out after {timeout} s")`; on `OSError` as e return `("unknown", f"failed to start: {e}")`. Reason strings exactly as §6.4 and §6.8. Exclude producer repos from the consumer set (§6, first paragraph). `render_verify` columns `Consumer | Evidence | Confidence | Contract | Tests | State | Reason`, followed by a one-line summary `pass=1 fail=1 not_run=0 unknown=1`. CLI: print "no consumers reference `x`" when empty; exit 2 if any `state == "fail"`.

- [ ] **Step 4: Write `docs/how-states-are-decided.md`** — the §6 rules in plain English with the parametrized table from the test.

- [ ] **Step 5: Run** → pass. **Step 6: Commit** — `git add -A && git commit -m "feat: verify with contract check, test runner and four states"`

---

### Task 9: MCP server and client check

**Files:**
- Create: `atlas/mcp_server.py`, `scripts/mcp_check.py`, `.mcp.json`, `opencode.json`, `tests/test_mcp.py`
- Modify: `atlas/cli.py` (`serve` subcommand)

**Interfaces:**
- Produces: `build_server(db_path: str) -> MCPServer` in `mcp_server.py` with tools `status`, `impact`, `verify`, `search`, `explain_edge` (§10); `atlas serve [--db]` runs it on stdio.

- [ ] **Step 1: Failing test** `tests/test_mcp.py` (uses the in-process client from the SDK; skip if `mcp` import fails):

```python
import asyncio, sys
from pathlib import Path
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from atlas.scan import scan_repos
FIX = Path(__file__).parent / "fixtures"

def test_mcp_tools_roundtrip(tmp_path):
    db = tmp_path / "a.db"
    scan_repos([FIX / "routes_repo", FIX / "consumer_repo"], db)
    async def go():
        params = StdioServerParameters(command=sys.executable, args=["-m", "atlas.cli", "serve", "--db", str(db)])
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                names = sorted(t.name for t in (await s.list_tools()).tools)
                assert names == ["explain_edge", "impact", "search", "status", "verify"]
                st = (await s.call_tool("status", {})).structured_content
                assert st["nodes"]["endpoint"] >= 5
                im = (await s.call_tool("impact", {"symbol": "customer_id"})).structured_content
                assert im["consumers"] and im["consumers"][0]["confidence"] in ("exact", "inferred")
                vr = (await s.call_tool("verify", {"symbol": "customer_id"})).structured_content
                assert set(vr["summary"]) == {"pass", "fail", "not_run", "unknown"}
    asyncio.run(go())
```

- [ ] **Step 2: Run** → fails. **Step 3: Implement** `mcp_server.py`: `from mcp.server.mcpserver import MCPServer`; `build_server(db_path)` creates `MCPServer("atlas", instructions="Cross-repo impact map with evidence. Call impact before editing a shared field; call verify after.")` and registers the five tools, each opening the DB per call (`open_db`) and returning `dataclasses.asdict`-based `dict[str, Any]`. Docstrings are the tool descriptions (write one clear sentence each, including what `symbol`, `renamed_to`, `run_tests` mean). Logging: `logging.basicConfig(stream=sys.stderr)`. CLI `serve`: `build_server(args.db).run(transport="stdio")`.

- [ ] **Step 4: Write** `scripts/mcp_check.py` (from `03-mcp-integration.md`), `.mcp.json` and `opencode.json` (from `03-…`).

- [ ] **Step 5: Run** `python -m pytest -q` → pass; `python scripts/mcp_check.py /tmp/t.db` prints the status JSON.

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: mcp server with status/impact/verify/search/explain_edge"`

---

### Task 10: Example workspace and end-to-end demo script

**Files:**
- Create: `examples/README.md`, `examples/demo.sh`, `examples/apply_rename.sh`, `examples/reset.sh`,
  `examples/backend/app.py`, `examples/backend/openapi.yaml`, `examples/backend/tests/test_app.py`,
  `examples/billing/charge.py`, `examples/billing/tests/test_charge.py`,
  `examples/web/profile.py`, `examples/web/tests/test_profile.py`,
  `examples/analytics/report.py`, `examples/analytics/data.csv`
- Test: `tests/test_e2e.py`

**Interfaces:** consumes the CLI only.

- [ ] **Step 1: Write the example repos** (exact contents):

`examples/backend/app.py`
```python
try:
    from fastapi import FastAPI
except ImportError:  # demo runs without FastAPI installed
    class FastAPI:
        def get(self, path):
            return lambda fn: fn

app = FastAPI()


@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {"id": user_id, "customer_id": f"C{user_id}", "email": f"user{user_id}@example.com"}
```

`examples/backend/openapi.yaml`
```yaml
openapi: 3.0.3
info: { title: Backend, version: "0.1" }
paths:
  /users/{user_id}:
    get:
      responses:
        "200":
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/User"
components:
  schemas:
    User:
      type: object
      properties:
        id: { type: integer }
        customer_id: { type: string }
        email: { type: string }
      example: { id: 1, customer_id: "C1", email: "user1@example.com" }
```

`examples/backend/tests/test_app.py`
```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app import get_user

def test_get_user_has_customer_id():
    assert get_user(1)["customer_id"] == "C1"
```

`examples/billing/tests/contract.py` **and** `examples/web/tests/contract.py` (identical copies, so each repo stays standalone):
```python
"""Load the backend's example response from its OpenAPI contract (keeps consumer tests honest)."""
import io, json, pathlib, yaml


def example_user() -> dict:
    spec = pathlib.Path(__file__).resolve().parents[2] / "backend" / "openapi.yaml"
    return yaml.safe_load(spec.read_text())["components"]["schemas"]["User"]["example"]


def fake_urlopen(url: str):
    """Stands in for urllib's urlopen: returns a file-like object with the contract example."""
    return io.BytesIO(json.dumps(example_user()).encode())
```

`examples/billing/charge.py` (stdlib only, so the demo needs no extra packages)
```python
import json
from urllib.request import urlopen

BASE = "http://localhost:8000"


def charge_user(user_id: int, amount: int) -> dict:
    with urlopen(f"{BASE}/users/{user_id}") as resp:
        data = json.load(resp)
    return {"customer": data["customer_id"], "amount": amount}
```

`examples/billing/tests/test_charge.py`
```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import charge
from contract import fake_urlopen


def test_charge_uses_backend_contract(monkeypatch):
    monkeypatch.setattr(charge, "urlopen", fake_urlopen)
    assert charge.charge_user(1, 500)["customer"] == "C1"
```

`examples/web/profile.py`
```python
import json
from urllib.request import urlopen

BASE = "http://localhost:8000"


def profile_label(user_id: int) -> str:
    with urlopen(f"{BASE}/users/{user_id}") as resp:
        user = json.load(resp)
    return f"{user['customer_id']} <{user['email']}>"
```

`examples/web/tests/test_profile.py` — same shape as billing's test (`monkeypatch.setattr(profile, "urlopen", fake_urlopen)`); asserts `profile_label(1).startswith("C1")`.

`examples/analytics/report.py`
```python
import csv


def customers(path: str) -> set[str]:
    with open(path, newline="") as f:
        return {row["customer_id"] for row in csv.DictReader(f)}
```
`examples/analytics/data.csv`: `customer_id,amount\nC1,500\nC2,250\n`

Note: the examples use only the standard library (`urllib`, `json`, `csv`) plus `pyyaml` in the test helper, which Atlas already installs. The demo needs **no** extra packages.

- [ ] **Step 2: Scripts**

`examples/apply_rename.sh` — simulates "the backend renamed the field and the web team updated, billing and analytics did not":
```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
sed -i.bak 's/customer_id/account_id/g' backend/app.py backend/openapi.yaml backend/tests/test_app.py web/profile.py
rm -f backend/*.bak backend/tests/*.bak web/*.bak
echo "renamed customer_id -> account_id in backend and web (billing and analytics untouched)"
```
`examples/reset.sh`: `git checkout -- "$(dirname "$0")"` (restores the examples).
`examples/demo.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export ATLAS_DB=./atlas.db
echo "## 1. scan";      atlas scan backend billing web analytics
echo "## 2. impact";    atlas impact customer_id
echo "## 3. change";    ./apply_rename.sh
echo "## 4. rescan";    atlas scan backend billing web analytics
echo "## 5. verify";    atlas verify customer_id --renamed-to account_id --run-tests || true
./reset.sh
```

- [ ] **Step 3: Expected output of step 5** (put this in `examples/README.md`; the e2e test asserts the states):

```
Consumer   Evidence        Confidence  Contract  Tests    State    Reason
---------  --------------  ----------  --------  -------  -------  ------------------------------------------------------------
analytics  report.py:6     inferred    fail      not_run  unknown  name match only; still references customer_id, which no producer exposes
billing    charge.py:10    exact       fail      fail     fail     still references customer_id, which no producer exposes
web        profile.py:10   exact       pass      pass     pass     updated to account_id
pass=1 fail=1 not_run=0 unknown=1
```
(Line numbers come from the files above: `report.py` line 6, `charge.py` line 10, `profile.py` line 10. Re-check after writing them.)

- [ ] **Step 4: E2E test** `tests/test_e2e.py`: copy `examples/` into `tmp_path`, run `main(["scan", ...])`, `main(["impact","customer_id","--json"])` and assert 3 consumer repos; run `apply_rename.sh` via `subprocess`, rescan, `verify ... --run-tests --json` and assert `{row.repo: row.state} == {"analytics": "unknown", "billing": "fail", "web": "pass"}` and exit code 2. Without `--run-tests`: `web == "not_run"`.

- [ ] **Step 5: Run** `python -m pytest -q` and `bash examples/demo.sh` → table as above. **Step 6: Commit** — `git add -A && git commit -m "feat: example workspace and demo script"`

---

### Task 11: README, docs, contributing, clean-install check

**Files:**
- Modify: `README.md`; Create: `CONTRIBUTING.md`, `docs/adding-an-extractor.md`, `.github/ISSUE_TEMPLATE/bug.md`, `.github/workflows/ci.yml`

- [ ] **Step 1: README structure** (write all sections; keep it scannable):
  1. One-line pitch + the verify table from the demo as the first thing a reader sees.
  2. Why: "agents and grep see one repo; this shows the system".
  3. Install: `pipx install git+https://github.com/<you>/atlas-repo-graph` or `uv tool install .`; verify with `atlas --help`.
  4. 60-second demo: `bash examples/demo.sh`.
  5. Commands (table): scan, status, impact, verify, search, explain-edge, serve. Exit codes.
  6. How states are decided (short table; link to docs).
  7. Use from a coding agent (MCP): the two config files + the prompt from `03-mcp-integration.md`.
  8. What it understands today (Python routes, OpenAPI, requests/httpx/urlopen, string-key field refs) and what it does not (list from `05-full-roadmap.md`).
  9. Prior art and how Atlas differs (from `10-reference-repos.md`): credit codebase-memory-mcp, repowise, repo-graph, CODEGRAPH_MCP, GitNexus.
  10. Contributing, license (MIT).
- [ ] **Step 2: `ci.yml`**: on push/PR, Python 3.11 and 3.12, `pip install -e ".[dev]"`, `python -m pytest -q`, `bash examples/demo.sh`.
- [ ] **Step 3: Clean-install check** in a fresh directory:
```bash
cd /tmp && rm -rf ci && git clone <local path or GitHub URL> ci && cd ci
uv venv .v && source .v/bin/activate && uv pip install -e ".[dev]" && python -m pytest -q && bash examples/demo.sh
```
Expected: tests pass; demo table printed.
- [ ] **Step 4: Commit** — `git add -A && git commit -m "docs: README, contributing, CI"`; create the public GitHub repo and push.

---

### Task 12: Demo video, X post, submission

Manual. Follow `07-demo-and-submission.md`. Do not start before Task 11 is green.

---

### Stretch A (only if Task 12 is done with ≥ 2 h left): `atlas explain` with an open model

- Create `atlas/explain.py`: `explain(rows: list[VerifyRow], symbol: str) -> str` posting to `ATLAS_MODEL_BASE_URL` (default `https://openrouter.ai/api/v1`) with `ATLAS_MODEL` (default `deepseek/deepseek-v4-flash`) and `ATLAS_MODEL_API_KEY`, using `urllib.request` (no new dependency). Prompt: "Here is a verification table… write 3 sentences for a PR description. Do not change any state." If no key: print "set ATLAS_MODEL_API_KEY to enable" and exit 1. Test with a fake `urlopen` via monkeypatch.

### Stretch B: `atlas graph --html out.html` — a single-file HTML with an inline SVG of repos as boxes and CALLS/CONSUMES as arrows (no JS libraries).

---

## Time plan (estimates)

| Task | Est. | Cumulative |
|---|---|---|
| 0 skeleton | 0:20 | 0:20 |
| 1 models + db | 0:40 | 1:00 |
| 2 openapi | 0:40 | 1:40 |
| 3 pyroutes | 0:45 | 2:25 |
| 4 pyconsumers | 1:00 | 3:25 |
| 5 link | 0:40 | 4:05 |
| 6 scan + cli | 0:45 | 4:50 |
| 7 impact/search | 0:45 | 5:35 |
| 8 verify | 1:00 | 6:35 |
| 9 mcp | 0:40 | 7:15 |
| 10 examples + e2e | 1:00 | 8:15 |
| 11 docs + clean install | 1:00 | 9:15 |
| 12 video + post + submit | 2:30 | 11:45 |

If behind schedule at Task 8: drop `search`/`explain-edge` from the MCP server (keep in CLI), skip Stretch A/B, keep Task 10–12 untouched.

## Dependency graph

```
0 → 1 → 2 ─┐
        3 ─┼→ 5 → 6 → 7 → 9 ─┐
        4 ─┘        └→ 8 ──┼→ 10 → 11 → 12
```
Tasks 2, 3, 4 are independent of each other (they only need Task 1). Everything else is sequential. Don't run parallel coding sessions on this plan: coordination costs more than it saves at this size.
