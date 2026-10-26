"""Rendering dataclasses to text (architecture §11). No logic here."""
from atlas.models import ImpactResult, VerifyRow


def render_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(str(cell)))
    lines = []
    lines.append("  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    lines.append("  ".join("-" * widths[i] for i in range(len(headers))))
    for row in rows:
        lines.append("  ".join(str(row[i]).ljust(widths[i]) if i < len(widths) else str(row[i])
                                for i in range(len(headers))))
    return "\n".join(lines)


def render_status(s: dict) -> str:
    lines = [f"DB: {s['db']}"]
    lines.append("")
    repo_rows = [[r["name"], r["path"], r.get("commit_sha") or "-",
                  r.get("test_cmd") or "-", r.get("scanned_at", "-")]
                 for r in s.get("repos", [])]
    lines.append(render_table(["Repo", "Path", "Commit", "Test cmd", "Scanned"], repo_rows))
    lines.append("")
    node_counts = s.get("nodes", {})
    edge_counts = s.get("edges", {})
    lines.append("Nodes: " + "  ".join(f"{k}={v}" for k, v in sorted(node_counts.items())))
    lines.append("Edges: " + "  ".join(f"{k}={v}" for k, v in sorted(edge_counts.items())))
    return "\n".join(lines)


def render_impact(r: ImpactResult) -> str:
    lines = [f"Symbol: {r.symbol}"]
    lines.append("")
    if r.producers:
        lines.append("Producers:")
        for p in r.producers:
            lines.append(f"  {p['repo']}  {p['endpoint']}  {p['file']}:{p['line']}")
    else:
        lines.append("Producers: (none)")
    lines.append("")
    if r.consumers:
        rows = [[c.repo, f"{c.file}:{c.line}", c.confidence, c.via, c.snippet]
                for c in r.consumers]
        lines.append(render_table(["Repo", "File:Line", "Confidence", "Via", "Snippet"], rows))
    else:
        lines.append("No consumers found.")
    return "\n".join(lines)


def render_verify(rows: list[VerifyRow]) -> str:
    if not rows:
        return ""
    table_rows = [
        [r.repo, r.evidence, r.confidence, r.contract, r.tests, r.state, r.reason]
        for r in rows
    ]
    headers = ["Consumer", "Evidence", "Confidence", "Contract", "Tests", "State", "Reason"]
    out = render_table(headers, table_rows)
    counts = {"pass": 0, "fail": 0, "not_run": 0, "unknown": 0}
    for r in rows:
        if r.state in counts:
            counts[r.state] += 1
    summary = " ".join(f"{k}={v}" for k, v in counts.items())
    return out + "\n" + summary
