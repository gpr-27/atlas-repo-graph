"""Scripted MCP client check: lists tools and calls atlas_status (no agent needed)."""
import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main(db: str):
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "atlas.cli", "serve", "--db", db],
    )
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            names = sorted(t.name for t in tools.tools)
            assert names == ["explain_edge", "impact", "search", "status", "verify"], \
                f"unexpected tools: {names}"
            print("Tools:", names)
            res = await s.call_tool("status", {})
            print(json.dumps(res.structured_content, indent=2))


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "atlas.db"))
