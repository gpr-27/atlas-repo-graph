# 10 — Reference repositories (what to learn, what not to copy)

Researched 26 Oct 2026 by reading the sources (shallow clones), not only READMEs. Stars are approximate.
**Licensing rule:** copy *ideas* from all; copy *code* from none (MIT ones you could, but Atlas is
small enough that borrowing designs is enough). Two are off-limits for code: repowise (AGPL-3.0) and
GitNexus (PolyForm Noncommercial).

| Repo | License | Stars | Lang | Closest to Atlas in… |
|---|---|---|---|---|
| [DeusData/codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp) | MIT | ~47.5k | C | cross-repo HTTP route matching, SQLite schema, MCP tools |
| [repowise-dev/repowise](https://github.com/repowise-dev/repowise) | **AGPL-3.0** | ~7.9k | Python | contracts + consumers + breaking-change rules (the closest feature set) |
| [James-Chahwan/repo-graph](https://github.com/James-Chahwan/repo-graph) | MIT | ~87 | Python (Rust engine) | polyrepo impact tool, honest "absence" reports |
| [raghurammrsd/CODEGRAPH_MCP](https://github.com/raghurammrsd/CODEGRAPH_MCP) | MIT | ~4 | Python | evidence columns on edges, `ast`-based Flask/FastAPI routes |
| [padobrik/mcp-context-graph](https://github.com/padobrik/mcp-context-graph) | MIT | ~2 | Python | minimal MCP server hygiene |
| [sdsrss/code-graph-mcp](https://github.com/sdsrss/code-graph-mcp) | MIT | ~86 | Rust | `confidence` enum on edges, unresolved-calls table |
| [abhigyanpatwari/GitNexus](https://github.com/abhigyanpatwari/GitNexus) | **PolyForm Noncommercial** | ~48k | TypeScript | response keys vs consumer keys ("shape check") |
| [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) | MIT | ~24.7k | Python | the `mcp` package itself |

(`brandyn-s/code-graph` returned 404; dropped.)

## What Atlas borrows, by task

### Path canonicalization (Task 2/3/4) — from codebase-memory-mcp `internal/cbm/route_path.c`
Every path parameter becomes the same placeholder regardless of style: `{id}`, `:id`, `<int:id>`, `${x}` → one segment. Atlas: `path_pattern()` turns each into `[^/]+`; consumer paths use `{}`. Parameter *names* are dropped so differently named variables still match.

### Route node shared by both sides (Task 5) — codebase-memory-mcp `src/pipeline/pass_route_nodes.c`
Client calls and server handlers meet at a canonical `"METHOD /path"` string. Atlas does the same: `http_call.name == "GET /users/{}"` matched against `endpoint.meta.pattern`.

### Evidence columns (Task 1) — CODEGRAPH_MCP `src/codegraph/indexing/indexer.py` (`graph_edges`)
`relationship, confidence, file, start_line, evidence, reason` on every edge. Atlas: `kind, confidence, ev_file, ev_line, ev_snippet, extractor, reason`. CODEGRAPH's rule "POSSIBLE is never upgraded" is Atlas's "inferred never becomes pass/fail".

### Two-level confidence (Task 5; roadmap S1) — repowise `origins.py` (design only)
`ORIGIN_CONFIDENCE`: OpenAPI 0.90, route registration 0.85, client call 0.75, name heuristic 0.65. Atlas keeps the two-word label (`exact`/`inferred`) as the user-facing truth and may add a numeric score later.

### Unresolved rows with a reason (Task 8; roadmap S2) — repowise `test_impact.py`, repo-graph `_render_absence`, sdsrss `pending_unresolved_calls`
A link that can't be followed comes back as a row with a reason, never silently dropped. Atlas: `not_run` / `unknown` rows always carry `reason`; `impact` on an unexposed symbol still lists name-matched consumers.

### Breaking-change rule for "removed field" (Task 8; roadmap V3) — repowise `breaking_change.py` (design only)
Impact is deliberately *direct*: provider → linked consumer files, no deep traversal. Atlas's contract check is exactly the `_removed_field` rule.

### Response keys vs consumer keys (Task 3/4) — GitNexus `response-shapes.ts`, `extractConsumerAccessedKeys` (concept only)
Producers: keys of the returned JSON literal. Consumers: keys read from the response. A consumer reading a key the producer doesn't return = mismatch. Atlas does this with `ast` instead of regex.

### MCP server hygiene (Task 9) — mcp-context-graph `mcp/server.py`, repo-graph `server.py`
Never `print()` in a stdio server; declare read-only tools (`ToolAnnotations(read_only_hint=True)` is available in the SDK if wanted); describe every parameter in the docstring.

### Tool naming (Task 9) — codebase-memory-mcp `src/mcp/mcp.c`, sdsrss `src/mcp/tools.rs`
Few, well-named tools with small parameter sets (`trace_path(symbol, direction, depth)`, `get_call_graph(route_path "GET /api/x")`). Atlas: five tools, ≤ 3 parameters each.

## What Atlas deliberately does not take
- Daemons, IPC, Cypher engines, LSP type resolution (codebase-memory-mcp).
- 100+ Alembic migrations, LLM doc generation, co-change edges (repowise).
- 97 tools, agent-brain modules (CODEGRAPH_MCP).
- Embeddings, Merkle resync (sdsrss).
- Rust engines, PageRank ranking (repo-graph).
- Web UI, taint analysis (GitNexus).

## How to describe the difference (README "Prior art" section)
> Several excellent tools build code graphs for agents (codebase-memory-mcp, repowise, repo-graph, CODEGRAPH_MCP, GitNexus). Atlas is deliberately smaller and stricter: it links *across* repositories, keeps the source evidence on every edge, and reports verification as pass / fail / not_run / unknown — never a green check it didn't earn. It is ~1,500 lines of Python you can read in an afternoon and extend with a 150-line extractor.
