"""CLI entry point (architecture §9)."""
import argparse
import dataclasses
import json
import os
import sqlite3
import sys
from pathlib import Path


def _db_default() -> str:
    return os.environ.get("ATLAS_DB", "./atlas.db")


def _version() -> str:
    from importlib.metadata import PackageNotFoundError, version
    try:
        return version("atlas-repo-graph")
    except PackageNotFoundError:
        return "unknown"


class _CLIError(Exception):
    def __init__(self, msg: str, code: int = 1):
        super().__init__(msg)
        self.code = code


def _open_db_or_exit(db_path: str):
    from atlas.db import open_db
    p = Path(db_path)
    if not p.exists():
        print(f"error: database not found: {db_path}", file=sys.stderr)
        raise _CLIError(f"database not found: {db_path}")
    return open_db(p)


def _cmd_scan(args) -> int:
    from atlas.scan import scan_repos
    paths = [Path(p) for p in args.repos]
    for p in paths:
        if not p.is_dir():
            print(f"error: repo path not found: {p}", file=sys.stderr)
            return 1
    try:
        result = scan_repos(paths, Path(args.db), verbose=args.verbose)
    except sqlite3.OperationalError as e:
        print(f"error: cannot open DB {args.db}: {e}", file=sys.stderr)
        return 1
    for r in result["repos"]:
        print(f"scanned {r['name']}: {r['nodes']} nodes, {r['edges']} edges, "
              f"{len(r['skipped'])} skipped")
    print(f"cross-repo edges: {result['cross_edges']}")
    return 0


def _cmd_status(args) -> int:
    from atlas.query import status
    from atlas.render import render_status
    conn = _open_db_or_exit(args.db)
    s = status(conn)
    conn.close()
    if args.json:
        print(json.dumps(s, indent=2))
    else:
        print(render_status(s))
    return 0


def _cmd_impact(args) -> int:
    from atlas.query import impact
    from atlas.render import render_impact
    conn = _open_db_or_exit(args.db)
    result = impact(conn, args.symbol)
    conn.close()
    if args.json:
        print(json.dumps(dataclasses.asdict(result), indent=2))
    else:
        print(render_impact(result))
    return 0


def _cmd_verify(args) -> int:
    from atlas.verify import verify
    from atlas.render import render_verify
    conn = _open_db_or_exit(args.db)
    rows = verify(conn, args.symbol,
                  renamed_to=args.renamed_to,
                  run_tests=args.run_tests,
                  timeout=args.timeout)
    conn.close()
    if not rows:
        print("[]" if args.json else f"no consumers reference `{args.symbol}`")
        return 0
    if args.json:
        print(json.dumps([dataclasses.asdict(r) for r in rows], indent=2))
    else:
        print(render_verify(rows))
    if any(r.state == "fail" for r in rows):
        return 2
    return 0


def _cmd_search(args) -> int:
    from atlas.query import search
    conn = _open_db_or_exit(args.db)
    hits = search(conn, args.text)
    conn.close()
    if args.json:
        print(json.dumps(hits, indent=2))
    else:
        from atlas.render import render_table
        rows = [[h["repo"], h["kind"], h["name"], f"{h['file']}:{h['line']}"] for h in hits]
        print(render_table(["Repo", "Kind", "Name", "File:Line"], rows))
    return 0


def _cmd_explain_edge(args) -> int:
    from atlas.query import explain_edge
    conn = _open_db_or_exit(args.db)
    result = explain_edge(conn, args.id)
    conn.close()
    if result is None:
        print(f"edge not found: {args.id}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        from atlas.render import render_table
        print(f"Edge {result['id']}: {result['kind']} ({result['confidence']})")
        print(f"  src: {result['src'].get('repo')} / {result['src'].get('file')}:{result['src'].get('line')} [{result['src'].get('kind')}] {result['src'].get('name')}")
        print(f"  dst: {result['dst'].get('repo')} / {result['dst'].get('file')}:{result['dst'].get('line')} [{result['dst'].get('kind')}] {result['dst'].get('name')}")
        ev = result["evidence"]
        print(f"  evidence: {ev['extractor']} {ev['file']}:{ev['line']}  {ev['snippet']}")
        if ev.get("reason"):
            print(f"  reason: {ev['reason']}")
    return 0


def _cmd_serve(args) -> int:
    from atlas.mcp_server import build_server
    build_server(args.db).run(transport="stdio")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="atlas", description="Cross-repo impact graph.")
    parser.add_argument("--version", action="version", version=f"atlas {_version()}")
    sub = parser.add_subparsers(dest="cmd")

    def _add_db(p):
        p.add_argument("--db", default=_db_default(), help="SQLite DB path (or ATLAS_DB env)")

    # scan
    p_scan = sub.add_parser("scan", help="Index repos into the DB")
    p_scan.add_argument("repos", nargs="+", help="Repo paths to scan")
    p_scan.add_argument("-v", "--verbose", action="store_true")
    _add_db(p_scan)

    # status
    p_st = sub.add_parser("status", help="Show DB summary")
    p_st.add_argument("--json", action="store_true")
    _add_db(p_st)

    # impact
    p_imp = sub.add_parser("impact", help="List producers and consumers of a symbol")
    p_imp.add_argument("symbol")
    p_imp.add_argument("--json", action="store_true")
    _add_db(p_imp)

    # verify
    p_ver = sub.add_parser("verify", help="Verify a symbol across consumer repos")
    p_ver.add_argument("symbol")
    p_ver.add_argument("--renamed-to", dest="renamed_to", default=None)
    p_ver.add_argument("--run-tests", action="store_true")
    p_ver.add_argument("--timeout", type=int, default=120)
    p_ver.add_argument("--json", action="store_true")
    _add_db(p_ver)

    # search
    p_srch = sub.add_parser("search", help="Substring search on node names")
    p_srch.add_argument("text")
    p_srch.add_argument("--json", action="store_true")
    _add_db(p_srch)

    # explain-edge
    p_ee = sub.add_parser("explain-edge", help="Show a single edge with evidence")
    p_ee.add_argument("id", type=int)
    p_ee.add_argument("--json", action="store_true")
    _add_db(p_ee)

    # serve
    p_srv = sub.add_parser("serve", help="Run MCP stdio server")
    _add_db(p_srv)

    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        # --help/--version exit 0; usage errors are 1 so they never look like a verify fail (2)
        return 0 if e.code in (0, None) else 1

    dispatch = {
        "scan": _cmd_scan,
        "status": _cmd_status,
        "impact": _cmd_impact,
        "verify": _cmd_verify,
        "search": _cmd_search,
        "explain-edge": _cmd_explain_edge,
        "serve": _cmd_serve,
    }
    if args.cmd not in dispatch:
        parser.print_help()
        return 1
    try:
        return dispatch[args.cmd](args)
    except _CLIError as e:
        return e.code
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
