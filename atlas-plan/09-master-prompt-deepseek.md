# 09 — Master prompt for the coding model (DeepSeek Flash or similar)

Paste everything between the lines into the coding agent at the start of the build. Then, for
each task, paste **only that task's section** from `04-mvp-implementation-plan.md` and say "Do Task N".

---

You are implementing **Atlas** (`atlas-repo-graph`), a small Python CLI + MCP server. The full design is in these files, which are the source of truth; read them before writing any code:

- `atlas-plan/01-product-spec.md` — what and why, requirements FR-001…FR-015, NFR-001…NFR-010.
- `atlas-plan/02-architecture.md` — every module, dataclass, table column, rule and signature. **Use these names exactly.**
- `atlas-plan/03-mcp-integration.md` — verified MCP 2.x server/client code.
- `atlas-plan/04-mvp-implementation-plan.md` — the ordered tasks. You will receive one task at a time.

## How you must work

1. **One task at a time.** Do only the task I give you. Do not start the next one. Do not "also improve" other files.
2. **Read before editing.** Open the files the task lists and the relevant sections of `02-architecture.md`. If an interface in the task differs from the architecture doc, the architecture doc wins; tell me.
3. **Tests first.** Write the test from the task card, run it, show me it fails, implement, run again, show me it passes. Paste the real pytest output. **Never claim a test passed without pasting the output.**
4. **No new dependencies.** Runtime: `pyyaml`, `mcp>=2,<3`. Dev: `pytest`. If you believe something else is needed, stop and ask with a one-line reason.
5. **No renames, no extra abstractions.** No base classes, plugin systems, config frameworks, or helpers that only one caller uses. Functions and dataclasses as specified.
6. **Keep facts deterministic.** Never call a model inside extractors, linker, query or verify. Confidence is `exact` or `inferred` by the rules in §5.5; state is only decided by `decide_state` per §6.
7. **Never print to stdout in `atlas/mcp_server.py`.** Use `logging` to stderr.
8. **Extractors never raise on bad input.** Catch `SyntaxError`, `UnicodeDecodeError`, `yaml.YAMLError`, `json.JSONDecodeError`, `OSError`; append `"file: reason"` to `skipped`.
9. **MCP 2.x API:** `from mcp.server.mcpserver import MCPServer`; `@mcp.tool()`; return `dict[str, Any]`; `mcp.run(transport="stdio")`. Do **not** use `FastMCP` or `mcp.server.fastmcp`.
10. **Commit at the end of each task** with the exact message in the task. Do not add `Co-Authored-By` lines.
11. **Report format at the end of every task:**
    - Files created/modified (list)
    - Commands run and their real output (pytest summary line at minimum)
    - Anything from the task you could not do, and why
    - Nothing else. No summaries of what the code "will" do.
12. **If blocked** (missing fact, contradictory instruction, failing test you cannot fix in 3 attempts): stop, show the exact error, and ask one specific question. Do not work around it by changing the spec.

## Things you must not do
- Do not modify `atlas-plan/`.
- Do not change `pyproject.toml` beyond what Task 0 specifies.
- Do not delete or weaken a test to make it pass.
- Do not use `print` for logging in library modules.
- Do not fetch URLs or call any API.
- Do not add type-checking, linting, or formatting tools unless asked.

## Environment
- macOS, Python ≥ 3.11 (`python3`), `uv` available. Create and use `.venv`.
- Run tests with `python -m pytest -q` from the repo root.

Acknowledge these rules in one sentence, then wait for "Do Task 0".

---
