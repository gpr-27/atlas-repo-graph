"""Scan orchestration (architecture §5.1)."""
import json
import subprocess
import sys
from pathlib import Path

import yaml

from atlas.db import fetch_nodes, fetch_repos, open_db, replace_cross_edges, replace_repo
from atlas.extract import iter_files
from atlas.extract.openapi import extract_openapi
from atlas.extract.pyconsumers import extract_py_consumers
from atlas.extract.pyroutes import extract_py_routes
from atlas.link import link
from atlas.models import ExtractResult, Node, RepoInfo


def git_head(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def detect_test_cmd(repo_root: Path) -> str | None:
    atlas_yaml = repo_root / ".atlas.yaml"
    if atlas_yaml.exists():
        try:
            data = yaml.safe_load(atlas_yaml.read_text())
            if isinstance(data, dict) and "test_cmd" in data:
                return data["test_cmd"]
        except Exception:
            pass
    if (repo_root / "pytest.ini").exists():
        return "python -m pytest -q"
    if (repo_root / "tests").is_dir():
        return "python -m pytest -q"
    if (repo_root / "setup.cfg").exists():
        try:
            text = (repo_root / "setup.cfg").read_text()
            if "[tool:pytest]" in text:
                return "python -m pytest -q"
        except Exception:
            pass
    if (repo_root / "pyproject.toml").exists():
        try:
            text = (repo_root / "pyproject.toml").read_text()
            if "pytest" in text:
                return "python -m pytest -q"
        except Exception:
            pass
    return None


def read_snippet(repo_root: Path, file: str, line: int, _cache: dict | None = None) -> str:
    if _cache is None:
        _cache = {}
    key = (str(repo_root), file)
    if key not in _cache:
        try:
            _cache[key] = (repo_root / file).read_text(encoding="utf-8").splitlines()
        except Exception:
            _cache[key] = []
    lines = _cache[key]
    if 0 < line <= len(lines):
        return lines[line - 1].strip()[:200]
    return ""


def _unique_name(base: str, seen: set[str]) -> str:
    if base not in seen:
        seen.add(base)
        return base
    i = 2
    while f"{base}-{i}" in seen:
        i += 1
    name = f"{base}-{i}"
    seen.add(name)
    return name


def _merge(parts: list[tuple[str, ExtractResult]]) -> ExtractResult:
    """Concatenate extractor results; skipped entries de-duplicated, first occurrence wins
    (a file with a SyntaxError is reported by both Python extractors)."""
    merged = ExtractResult()
    for _, part in parts:
        merged.nodes.extend(part.nodes)
        merged.edges.extend(part.edges)
        merged.skipped.extend(part.skipped)
    merged.skipped = list(dict.fromkeys(merged.skipped))
    return merged


def _print_per_file(parts: list[tuple[str, ExtractResult]]) -> None:
    """NFR-009: per-file node counts, broken down by the extractor that produced them."""
    per_file: dict[str, dict[str, int]] = {}
    for extractor, part in parts:
        for node in part.nodes:
            counts = per_file.setdefault(node.file, {})
            counts[extractor] = counts.get(extractor, 0) + 1
    for file, counts in sorted(per_file.items()):
        detail = ", ".join(f"{ext} {n}" for ext, n in counts.items())
        print(f"    {file}: {sum(counts.values())} nodes ({detail})", file=sys.stderr)


def scan_repos(
    paths: list[Path], db_path: Path, verbose: bool = False
) -> dict:
    db_path = Path(db_path)
    conn = open_db(db_path)

    seen_names: set[str] = set()
    repo_infos: list[RepoInfo] = []
    for p in paths:
        p = Path(p).resolve()
        name = _unique_name(p.name, seen_names)
        repo_infos.append(RepoInfo(name, str(p), git_head(p), detect_test_cmd(p)))

    # First pass: producer extraction to collect known field names
    snippet_cache: dict = {}
    producer_results: list[tuple[RepoInfo, list[tuple[str, ExtractResult]]]] = []
    all_known_fields: set[str] = set()
    for repo_info in repo_infos:
        p = Path(repo_info.path)
        parts = [
            ("openapi", extract_openapi(repo_info.name, p)),
            ("pyroutes", extract_py_routes(repo_info.name, p)),
        ]
        producer_results.append((repo_info, parts))
        for _, part in parts:
            all_known_fields.update(n.name for n in part.nodes if n.kind == "field")
    # Fields already indexed from repos that are NOT part of this call still count as known.
    scanning = {r.name for r in repo_infos}
    all_known_fields.update(
        row["name"] for row in fetch_nodes(conn, kind="field") if row["repo"] not in scanning
    )

    summary_repos = []

    for repo_info, parts in producer_results:
        p = Path(repo_info.path)
        parts = parts + [("pyconsumers", extract_py_consumers(repo_info.name, p, all_known_fields))]
        combined = _merge(parts)
        counts = replace_repo(conn, repo_info, combined.nodes, combined.edges, {})

        if verbose:
            print(
                f"  {repo_info.name}: {counts['nodes']} nodes, {counts['edges']} edges, "
                f"{len(combined.skipped)} skipped",
                file=sys.stderr,
            )
            _print_per_file(parts)
            for s in combined.skipped:
                print(f"    skipped: {s}", file=sys.stderr)

        summary_repos.append({
            "name": repo_info.name,
            "nodes": counts["nodes"],
            "edges": counts["edges"],
            "skipped": combined.skipped,
        })

    # Cross-repo linking runs over every node in the DB (not just the repos passed to this
    # call), so re-scanning one repo never drops links that involve other indexed repos.
    repo_paths = {r["name"]: Path(r["path"]) for r in fetch_repos(conn)}
    all_nodes: list[Node] = []
    all_snippets: dict[str, str] = {}
    for row in fetch_nodes(conn):
        node = Node(row["repo"], row["kind"], row["name"], row["file"], row["line"], json.loads(row["meta"]))
        all_nodes.append(node)
        all_snippets[node.key] = read_snippet(repo_paths[row["repo"]], node.file, node.line, snippet_cache)
    cross_edges = link(all_nodes, all_snippets)
    n_cross = replace_cross_edges(conn, cross_edges)

    if verbose:
        print(f"  cross-repo edges: {n_cross}", file=sys.stderr)

    conn.close()
    return {"repos": summary_repos, "cross_edges": n_cross}
