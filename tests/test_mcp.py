import asyncio
import sys
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
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "atlas.cli", "serve", "--db", str(db)],
        )
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


def test_mcp_missing_db_is_an_error_not_an_empty_answer(tmp_path):
    db = tmp_path / "none.db"

    async def go():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "atlas.cli", "serve", "--db", str(db)],
        )
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                try:
                    res = await s.call_tool("impact", {"symbol": "customer_id"})
                except Exception as e:  # some client versions raise MCPError
                    return str(e)
                assert res.is_error
                return " ".join(getattr(c, "text", "") for c in res.content)

    assert "not found" in asyncio.run(go())
    assert not db.exists()
