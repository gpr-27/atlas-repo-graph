"""Query functions: status, impact, search, explain_edge (architecture §7)."""
import json
import sqlite3
from dataclasses import asdict

from atlas.models import ImpactResult, ImpactRow


def status(conn: sqlite3.Connection) -> dict:
    db_path = conn.execute("PRAGMA database_list").fetchone()[2]
    repos = [dict(r) for r in conn.execute(
        "SELECT name, path, commit_sha, test_cmd, scanned_at FROM repos ORDER BY name"
    ).fetchall()]
    node_counts = {
        row[0]: row[1]
        for row in conn.execute("SELECT kind, COUNT(*) FROM nodes GROUP BY kind").fetchall()
    }
    edge_counts = {
        row[0]: row[1]
        for row in conn.execute("SELECT kind, COUNT(*) FROM edges GROUP BY kind").fetchall()
    }
    return {"db": db_path, "repos": repos, "nodes": node_counts, "edges": edge_counts}


def impact(conn: sqlite3.Connection, symbol: str) -> ImpactResult:
    # Find field nodes named symbol
    field_rows = conn.execute(
        "SELECT n.id, n.file, n.line, n.meta, r.name AS repo "
        "FROM nodes n JOIN repos r ON r.id = n.repo_id "
        "WHERE n.kind = 'field' AND n.name = ?",
        (symbol,),
    ).fetchall()

    field_ids = [r["id"] for r in field_rows]

    # Build producers list: join via meta.endpoint
    producers = []
    for row in field_rows:
        meta = json.loads(row["meta"]) if row["meta"] else {}
        producers.append({
            "repo": row["repo"],
            "endpoint": meta.get("endpoint", ""),
            "file": row["file"],
            "line": row["line"],
        })

    # Repos that expose the symbol (producers) — exclude from consumers
    producer_repos = {p["repo"] for p in producers}

    consumers: list[ImpactRow] = []

    if field_ids:
        # CONSUMES edges pointing to these fields
        placeholders = ",".join("?" * len(field_ids))
        edge_rows = conn.execute(
            f"SELECT e.id, e.src_id, e.dst_id, e.confidence, e.ev_snippet, e.ev_file, e.ev_line, e.reason "
            f"FROM edges e WHERE e.kind = 'CONSUMES' AND e.dst_id IN ({placeholders})",
            field_ids,
        ).fetchall()

        for er in edge_rows:
            # get source node (consumer)
            src = conn.execute(
                "SELECT n.name, n.file, n.line, r.name AS repo "
                "FROM nodes n JOIN repos r ON r.id = n.repo_id WHERE n.id = ?",
                (er["src_id"],),
            ).fetchone()
            if src is None or src["repo"] in producer_repos:
                continue
            # get dst field's endpoint
            dst = conn.execute(
                "SELECT n.meta FROM nodes n WHERE n.id = ?", (er["dst_id"],)
            ).fetchone()
            dst_meta = json.loads(dst["meta"]) if dst and dst["meta"] else {}
            via = dst_meta.get("endpoint", "") if er["confidence"] == "exact" else "name match"
            consumers.append(ImpactRow(
                repo=src["repo"],
                file=src["file"],
                line=src["line"],
                snippet=er["ev_snippet"],
                confidence=er["confidence"],
                via=via,
                edge_id=er["id"],
            ))
    else:
        # No producers: field_refs named symbol → orphan rows (inferred, edge_id=0)
        ref_rows = conn.execute(
            "SELECT n.file, n.line, r.name AS repo "
            "FROM nodes n JOIN repos r ON r.id = n.repo_id "
            "WHERE n.kind = 'field_ref' AND n.name = ?",
            (symbol,),
        ).fetchall()
        for rr in ref_rows:
            consumers.append(ImpactRow(
                repo=rr["repo"], file=rr["file"], line=rr["line"],
                snippet="", confidence="inferred", via="name match", edge_id=0,
            ))

    return ImpactResult(symbol=symbol, producers=producers, consumers=consumers)


def search(conn: sqlite3.Connection, text: str, limit: int = 50) -> list[dict]:
    pattern = f"%{text}%"
    rows = conn.execute(
        "SELECT n.id, n.kind, n.name, n.file, n.line, r.name AS repo "
        "FROM nodes n JOIN repos r ON r.id = n.repo_id "
        "WHERE LOWER(n.name) LIKE LOWER(?) "
        "ORDER BY n.id LIMIT ?",
        (pattern, limit),
    ).fetchall()
    return [{"id": r["id"], "repo": r["repo"], "kind": r["kind"],
             "name": r["name"], "file": r["file"], "line": r["line"]} for r in rows]


def explain_edge(conn: sqlite3.Connection, edge_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM edges WHERE id = ?", (edge_id,)).fetchone()
    if row is None:
        return None

    def _node_dict(node_id: int) -> dict:
        n = conn.execute(
            "SELECT n.*, r.name AS repo FROM nodes n JOIN repos r ON r.id = n.repo_id WHERE n.id = ?",
            (node_id,),
        ).fetchone()
        if n is None:
            return {}
        return {"id": n["id"], "repo": n["repo"], "kind": n["kind"],
                "name": n["name"], "file": n["file"], "line": n["line"]}

    return {
        "id": row["id"],
        "kind": row["kind"],
        "confidence": row["confidence"],
        "src": _node_dict(row["src_id"]),
        "dst": _node_dict(row["dst_id"]),
        "evidence": {
            "file": row["ev_file"],
            "line": row["ev_line"],
            "snippet": row["ev_snippet"],
            "extractor": row["extractor"],
            "reason": row["reason"],
        },
    }
