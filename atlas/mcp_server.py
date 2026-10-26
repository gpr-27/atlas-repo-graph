"""MCP stdio server (architecture §10). Never prints to stdout — that is the protocol channel."""
import dataclasses
import logging
import os
import sys
from typing import Any

from mcp.server.mcpserver import MCPServer

logging.basicConfig(stream=sys.stderr, level=logging.WARNING)


def build_server(db_path: str) -> MCPServer:
    mcp = MCPServer(
        "atlas",
        instructions=(
            "Cross-repo impact map with evidence on every edge. "
            "Call impact before editing a shared field; call verify after."
        ),
    )

    def _conn():
        from atlas.db import open_db
        return open_db(db_path)

    @mcp.tool()
    def status() -> dict[str, Any]:
        """Return repos indexed, node/edge counts by kind, last scan time, and DB path."""
        from atlas.query import status as q_status
        conn = _conn()
        try:
            return q_status(conn)
        finally:
            conn.close()

    @mcp.tool()
    def impact(symbol: str) -> dict[str, Any]:
        """Return every producer and consumer of symbol, with file:line evidence and confidence.
        symbol: the field name to look up (e.g. 'customer_id')."""
        from atlas.query import impact as q_impact
        conn = _conn()
        try:
            return dataclasses.asdict(q_impact(conn, symbol))
        finally:
            conn.close()

    @mcp.tool()
    def verify(
        symbol: str,
        renamed_to: str | None = None,
        run_tests: bool = False,
    ) -> dict[str, Any]:
        """Check every consumer repo for contract and test state after a field change.
        symbol: the original field name.
        renamed_to: new name if the field was renamed.
        run_tests: set true to actually run each consumer repo's test suite."""
        from atlas.verify import verify as q_verify
        conn = _conn()
        try:
            rows = q_verify(conn, symbol, renamed_to=renamed_to, run_tests=run_tests)
        finally:
            conn.close()
        row_dicts = [dataclasses.asdict(r) for r in rows]
        summary = {"pass": 0, "fail": 0, "not_run": 0, "unknown": 0}
        for r in rows:
            if r.state in summary:
                summary[r.state] += 1
        return {"rows": row_dicts, "summary": summary}

    @mcp.tool()
    def search(text: str) -> dict[str, Any]:
        """Case-insensitive substring search across all node names.
        text: substring to search for."""
        from atlas.query import search as q_search
        conn = _conn()
        try:
            return {"results": q_search(conn, text)}
        finally:
            conn.close()

    @mcp.tool()
    def explain_edge(edge_id: int) -> dict[str, Any]:
        """Return a single edge with both endpoint nodes and full evidence.
        edge_id: the integer edge ID (from an impact or search result)."""
        from atlas.query import explain_edge as q_explain
        conn = _conn()
        try:
            result = q_explain(conn, edge_id)
            return result if result is not None else {"error": "not found"}
        finally:
            conn.close()

    return mcp
