# Atlas — cross-repo impact map

> After renaming `customer_id` → `account_id` in the backend:
>
> ```
> Consumer   Evidence       Confidence  Contract  Tests    State    Reason
> ---------  -------------  ----------  --------  -------  -------  ------------------------------------------------------------------------
> analytics  report.py:6    inferred    fail      not_run  unknown  name match only; still references customer_id, which no producer exposes
> billing    charge.py:10   exact       fail      fail     fail     still references customer_id, which no producer exposes
> web        profile.py:10  exact       pass      pass     pass     updated to account_id
> pass=1 fail=1 not_run=0 unknown=1
> ```

Atlas maps how your local git repositories depend on each other — HTTP endpoints and response fields → the code in other repos that uses them — shows what a change would break, proves every link with file-and-line evidence, and reports one of four honest states: **pass / fail / not_run / unknown**.

It runs as a CLI (`atlas`) and as an MCP server so any coding agent (Claude Code, Cursor, Codex, opencode …) can call `atlas_impact` before editing a shared field.

## Why

Agents and `grep` see one repo at a time. A change that looks safe in the backend silently breaks the billing job and the analytics script two repos over. Atlas is the shared map: deterministic, local, no account, no network, queryable by any agent over MCP.

## Install

```bash
# from a clone, into a virtualenv (includes pytest)
pip install -e ".[dev]"
# or as an isolated tool
uv tool install . --with pytest

# verify
atlas --help
```

Replace `YOUR_GITHUB_USERNAME` when the repo is public:
```bash
pipx install git+https://github.com/YOUR_GITHUB_USERNAME/atlas-repo-graph
pipx inject atlas-repo-graph pytest
```

**Why pytest?** `atlas verify --run-tests` runs each consumer repo's test command (`python -m pytest -q` by default) with the *same Python Atlas is installed in*. If pytest is missing from that environment, no test can run, so Atlas reports `tests: unknown` ("failed to start") rather than a pass or fail it didn't earn — and the demo can't show `web pass`. Install pytest alongside Atlas as shown above, or give the repo a `.atlas.yaml` whose `test_cmd:` does not start with `python ` (for example `make test`), which Atlas runs unchanged.

## 60-second demo

```bash
bash examples/demo.sh
```

This scans four tiny repos, shows the impact of `customer_id`, renames it in backend+web, rescans, and verifies — producing the table above.

## Commands

| Command | What it does | Exit code |
|---|---|---|
| `atlas scan <repo>...` | Index repos into the DB; `--db` sets path | 0 |
| `atlas status` | Repos, node/edge counts, last scan | 0 |
| `atlas impact <symbol>` | Producers + consumers with evidence | 0 |
| `atlas verify <symbol> [--renamed-to NEW] [--run-tests]` | Per-consumer contract + test state | 0 / **2** if any fail |
| `atlas search <text>` | Substring match on node names | 0 |
| `atlas explain-edge <id>` | One edge with full evidence | 0 / 1 if not found |
| `atlas --version` | Print the installed version | 0 |
| `atlas serve` | MCP stdio server | — |

`--db` defaults to `$ATLAS_DB` env var or `./atlas.db`. Usage errors and a missing DB exit 1, so exit 2 always means a verify `fail`. Add `-v` to `scan` for per-file counts.

## How states are decided

Rules are applied in this order (first match wins; this is `decide_state` in `atlas/verify.py`):

| # | Condition | State |
|---|---|---|
| 1 | confidence is `inferred` (name match only) | **unknown** |
| 2 | contract is `fail` **or** tests are `fail` | **fail** |
| 3 | tests are `pass` | **pass** |
| 4 | contract is `pass` and tests are `not_run` | **not_run** |
| 5 | anything else (e.g. contract `n/a`, or tests `unknown`) | **unknown** |

`state == pass` only when tests actually ran and passed **and** the link is exact (NFR-006). See [`docs/how-states-are-decided.md`](docs/how-states-are-decided.md).

## Use from a coding agent (MCP)

Atlas speaks MCP over stdio — works with Claude Code, Cursor, Codex, opencode, and any other MCP-capable agent.

**Claude Code** — add to `.mcp.json` at your project root:
```json
{
  "mcpServers": {
    "atlas": { "command": "atlas", "args": ["serve", "--db", "./atlas.db"] }
  }
}
```

**opencode** — add to `opencode.json`:
```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "atlas": { "type": "local", "command": ["atlas", "serve", "--db", "./atlas.db"], "enabled": true }
  }
}
```

The server reads an existing index; it never creates one. Build it first — from this repo's root, so the committed `.mcp.json` finds `./atlas.db`:
```bash
atlas scan examples/backend examples/billing examples/web examples/analytics
```
If the DB is missing, every tool returns an error ("Atlas DB not found … run `atlas scan` first") instead of an empty answer that would look like "nobody uses this field".

**Any other agent** — run `atlas serve --db ./atlas.db`; the server exposes `impact`, `verify`, `search`, `status`, `explain_edge`; most agents show them prefixed with the server name (`atlas_impact`, `atlas_verify`, …).

**Example agent prompt:**
> Rename `customer_id` to `account_id` in the users endpoint. Before editing, call `atlas_impact` to find every consumer, then update them, then call `atlas_verify` with `run_tests=true` and report the table.

Verify the server works without an agent:
```bash
atlas scan examples/backend examples/billing examples/web examples/analytics
python scripts/mcp_check.py ./atlas.db
```

## What Atlas understands today

**Producers** — Python route decorators (`@app.get`, `@router.post`, `@app.route`, …) and OpenAPI 3.x files (`openapi.yaml/json`). Dict-literal and `jsonify({…})` returns become field nodes.

**Consumers** — `requests.*`, `httpx.*`, `urlopen` HTTP calls; `x["f"]`, `x.get("f")`, `x.f` field references (attribute access only for known field names).

**What it does not understand (yet)** — TypeScript/Go/Java; gRPC, GraphQL, event queues; runtime tracing; dynamic field keys; nested `$ref` beyond one level. See [`atlas-plan/05-full-roadmap.md`](atlas-plan/05-full-roadmap.md).

## What makes it different

- **Cross-repo with evidence on every edge** — you can click to the file and line.
- **Four honest states** — a truthful `unknown` beats a false green check.
- **Agent-first via MCP** — ready for any coding agent in two minutes.
- **Small enough to read in an afternoon** — ~1,800 lines of Python; a language extractor is ~150 lines.

## Prior art

Several excellent tools build code graphs for agents. Atlas borrows *ideas* from them (no code is copied) and credits what each is closest to:

| Tool | Licence | Closest to Atlas in |
|---|---|---|
| [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | MIT | cross-repo HTTP route matching, SQLite schema, MCP tools |
| [repowise](https://github.com/repowise-dev/repowise) | AGPL-3.0 | contracts + consumers + breaking-change rules |
| [repo-graph](https://github.com/James-Chahwan/repo-graph) | MIT | polyrepo impact, honest "absence" reports |
| [CODEGRAPH_MCP](https://github.com/raghurammrsd/CODEGRAPH_MCP) | MIT | evidence columns on edges, `ast`-based Flask/FastAPI routes |
| [GitNexus](https://github.com/abhigyanpatwari/GitNexus) | PolyForm Noncommercial | response keys vs consumer keys ("shape check") |

Atlas is deliberately smaller and stricter: it links *across* repositories, keeps the source evidence on every edge, and reports verification as pass / fail / not_run / unknown — never a green check it didn't earn. It is a small codebase you can read in an afternoon and extend with a ~150-line extractor.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The codebase is intentionally small: one module per concern, pure functions for extractors, no magic.

To add a language extractor, see [`docs/adding-an-extractor.md`](docs/adding-an-extractor.md).

## License

MIT © 2026. See [LICENSE](LICENSE).
