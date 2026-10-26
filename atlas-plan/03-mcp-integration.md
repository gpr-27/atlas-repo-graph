# 03 — MCP integration (how any coding agent uses Atlas)

Atlas exposes its queries as **MCP tools over stdio**. MCP (Model Context Protocol) is the standard
most coding agents use to call external tools. This is generic: nothing here is vendor-specific.

## Verified facts (tested on this machine, 26 Oct 2026)

- PyPI `mcp` **2.3.0**. In 2.x the server class is `MCPServer` (old name `FastMCP` raises `ModuleNotFoundError` with a migration hint).
- Minimal server that works:

```python
# atlas/mcp_server.py (shape)
from typing import Any
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("atlas", instructions="Cross-repo impact graph with evidence.")

@mcp.tool()
def status() -> dict[str, Any]:
    """Repos indexed, node/edge counts, last scan."""
    ...

if __name__ == "__main__":
    mcp.run(transport="stdio")
```
- Return type **must** be annotated `dict[str, Any]` (or a pydantic model) for the client to receive `structured_content`; a bare `dict` annotation returned `None` for structured content in the test.
- Client-side check that works (use in `scripts/mcp_check.py`):

```python
import asyncio, json, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main(db: str):
    params = StdioServerParameters(command=sys.executable, args=["-m", "atlas.cli", "serve", "--db", db])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            names = sorted(t.name for t in tools.tools)
            assert names == ["explain_edge", "impact", "search", "status", "verify"], names
            res = await s.call_tool("status", {})
            print(json.dumps(res.structured_content, indent=2))

asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "atlas.db"))
```
- v2 client API notes: result fields are snake_case (`structured_content`, `is_error`); tool errors raise `MCPError` on the client.
- The server must write logs to **stderr** only. Anything printed to stdout corrupts the protocol.

## Agent configuration files (commit both to the repo)

Tool names as seen by the agent are usually `<server>_<tool>`, e.g. `atlas_impact`.

**Claude Code** — `.mcp.json` at project root:
```json
{
  "mcpServers": {
    "atlas": {
      "command": "atlas",
      "args": ["serve", "--db", "./atlas.db"]
    }
  }
}
```

**opencode** — `opencode.json` at project root (format from opencode docs):
```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "atlas": {
      "type": "local",
      "command": ["atlas", "serve", "--db", "./atlas.db"],
      "enabled": true
    }
  }
}
```

**Cursor / Codex / others** — same idea: command `atlas`, args `serve --db <path>`. Document in README as "any MCP client: run `atlas serve`".

If `atlas` is not on PATH for the agent, use the absolute path printed by `which atlas`, or `python -m atlas.cli serve`.

## How an agent uses it (what to show in the demo)

Prompt to the agent, in the `backend` repo:
> Rename the `customer_id` field to `account_id` in the users endpoint. Before editing, use the atlas impact tool to find every consumer, then update them, then run atlas verify with run_tests=true and report the table.

Expected tool calls: `atlas_impact(symbol="customer_id")` → edits → `atlas_verify(symbol="customer_id", renamed_to="account_id", run_tests=True)`.

## Fallbacks
- If the agent cannot load MCP: the CLI gives identical results; the agent can run `atlas impact customer_id --json` in a shell.
- If `mcp` import fails: `atlas serve` prints a clear error ("install atlas-repo-graph[mcp]") and exits 1; everything else still works. (MVP keeps `mcp` as a hard dependency for simplicity; roadmap makes it an extra.)
