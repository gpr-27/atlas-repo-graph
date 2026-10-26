"""The only module that imports sqlite3 (architecture §3)."""
import sqlite3
from pathlib import Path

from atlas.models import Edge, Node, RepoInfo

SCHEMA = """
CREATE TABLE IF NOT EXISTS repos (
  id          INTEGER PRIMARY KEY,
  name        TEXT NOT NULL UNIQUE,
  path        TEXT NOT NULL,
  commit_sha  TEXT,
  test_cmd    TEXT,
  scanned_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nodes (
  id      INTEGER PRIMARY KEY,
  repo_id INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
  kind    TEXT NOT NULL,
  name    TEXT NOT NULL,
  file    TEXT NOT NULL,
  line    INTEGER NOT NULL,
  meta    TEXT NOT NULL DEFAULT '{}',
  UNIQUE (repo_id, kind, name, file, line, meta)
);
CREATE INDEX IF NOT EXISTS nodes_kind_name ON nodes(kind, name);

CREATE TABLE IF NOT EXISTS edges (
  id          INTEGER PRIMARY KEY,
  src_id      INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
  dst_id      INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
  kind        TEXT NOT NULL,
  confidence  TEXT NOT NULL,
  ev_file     TEXT NOT NULL,
  ev_line     INTEGER NOT NULL,
  ev_snippet  TEXT NOT NULL,
  extractor   TEXT NOT NULL,
  reason      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS edges_dst ON edges(dst_id);
CREATE INDEX IF NOT EXISTS edges_src ON edges(src_id);
"""


def open_db(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.execute("PRAGMA user_version=1")
    conn.commit()


def _key(repo: str, kind: str, name: str, file: str, line: int, meta: str) -> str:
    return f"{repo}|{kind}|{name}|{file}|{line}|{meta}"


def _key_to_id(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT n.id, n.kind, n.name, n.file, n.line, n.meta, r.name AS repo "
        "FROM nodes n JOIN repos r ON r.id = n.repo_id"
    ).fetchall()
    return {
        _key(row["repo"], row["kind"], row["name"], row["file"], row["line"], row["meta"]): row["id"]
        for row in rows
    }


def _insert_edges(conn: sqlite3.Connection, edges: list[Edge], ids: dict[str, int]) -> int:
    inserted = 0
    for edge in edges:
        src_id = ids.get(edge.src_key)
        dst_id = ids.get(edge.dst_key)
        if src_id is None or dst_id is None:
            continue
        cur = conn.execute(
            "INSERT INTO edges (src_id, dst_id, kind, confidence, ev_file, ev_line, ev_snippet, extractor, reason) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                src_id,
                dst_id,
                edge.kind,
                edge.confidence,
                edge.evidence.file,
                edge.evidence.line,
                edge.evidence.snippet,
                edge.evidence.extractor,
                edge.evidence.reason,
            ),
        )
        inserted += 1 if cur.rowcount else 0
    return inserted


def replace_repo(
    conn: sqlite3.Connection,
    repo: RepoInfo,
    nodes: list[Node],
    edges: list[Edge],
    snippets: dict[str, str],
) -> dict[str, int]:
    del snippets  # the snippet text is carried on each Edge's evidence
    conn.execute("DELETE FROM repos WHERE name = ?", (repo.name,))
    conn.execute(
        "INSERT INTO repos (name, path, commit_sha, test_cmd, scanned_at) "
        "VALUES (?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))",
        (repo.name, repo.path, repo.commit_sha, repo.test_cmd),
    )
    repo_id = conn.execute("SELECT id FROM repos WHERE name = ?", (repo.name,)).fetchone()["id"]
    node_count = 0
    for node in nodes:
        cur = conn.execute(
            "INSERT OR IGNORE INTO nodes (repo_id, kind, name, file, line, meta) VALUES (?, ?, ?, ?, ?, ?)",
            (repo_id, node.kind, node.name, node.file, node.line, node.meta_json),
        )
        node_count += 1 if cur.rowcount else 0
    edge_count = _insert_edges(conn, edges, _key_to_id(conn))
    conn.commit()
    return {"nodes": node_count, "edges": edge_count}


def replace_cross_edges(conn: sqlite3.Connection, edges: list[Edge]) -> int:
    conn.execute("DELETE FROM edges WHERE kind IN ('CALLS','CONSUMES')")
    count = _insert_edges(conn, edges, _key_to_id(conn))
    conn.commit()
    return count


def node_id_by_key(conn: sqlite3.Connection, key: str) -> int | None:
    return _key_to_id(conn).get(key)


def fetch_nodes(
    conn: sqlite3.Connection, kind: str | None = None, name: str | None = None
) -> list[sqlite3.Row]:
    sql = (
        "SELECT n.*, r.name AS repo FROM nodes n JOIN repos r ON r.id = n.repo_id"
    )
    clauses: list[str] = []
    params: list[str] = []
    if kind is not None:
        clauses.append("n.kind = ?")
        params.append(kind)
    if name is not None:
        clauses.append("n.name = ?")
        params.append(name)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY n.id"
    return conn.execute(sql, params).fetchall()


def fetch_edges(
    conn: sqlite3.Connection,
    kind: str | None = None,
    dst_id: int | None = None,
    src_id: int | None = None,
) -> list[sqlite3.Row]:
    sql = "SELECT * FROM edges"
    clauses: list[str] = []
    params: list[int | str] = []
    if kind is not None:
        clauses.append("kind = ?")
        params.append(kind)
    if dst_id is not None:
        clauses.append("dst_id = ?")
        params.append(dst_id)
    if src_id is not None:
        clauses.append("src_id = ?")
        params.append(src_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id"
    return conn.execute(sql, params).fetchall()


def fetch_repos(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM repos ORDER BY name").fetchall()