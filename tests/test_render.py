"""Unit tests for atlas/render.py — no DB, no scan, pure function checks."""
from atlas.models import ImpactResult, ImpactRow, VerifyRow
from atlas.render import render_table, render_status, render_impact, render_verify


def test_render_table_aligns_columns():
    out = render_table(["A", "BB", "CCC"], [["x", "yy", "zzz"], ["long_val", "b", "c"]])
    lines = out.splitlines()
    assert lines[0].startswith("A")
    assert "BB" in lines[0]
    # header underline uses dashes
    assert all(c in "-  " for c in lines[1])
    # data rows present
    assert any("long_val" in l for l in lines)


def test_render_table_empty_rows():
    out = render_table(["X", "Y"], [])
    lines = out.splitlines()
    assert len(lines) == 2  # header + underline only


def test_render_status_contains_repo_and_counts():
    s = {
        "db": "/tmp/a.db",
        "repos": [{"name": "backend", "path": "/x", "commit_sha": "abc", "test_cmd": None, "scanned_at": "2026-01-01"}],
        "nodes": {"endpoint": 2, "field": 3},
        "edges": {"EXPOSES": 3, "CALLS": 1},
    }
    out = render_status(s)
    assert "backend" in out
    assert "endpoint=2" in out
    assert "EXPOSES=3" in out
    assert "/tmp/a.db" in out


def test_render_impact_producers_and_consumers():
    r = ImpactResult(
        symbol="customer_id",
        producers=[{"repo": "backend", "endpoint": "GET /users/{user_id}", "file": "app.py", "line": 5}],
        consumers=[ImpactRow(repo="billing", file="charge.py", line=10,
                             snippet='data["customer_id"]', confidence="exact",
                             via="GET /users/{user_id}", edge_id=1)],
    )
    out = render_impact(r)
    assert "customer_id" in out
    assert "backend" in out
    assert "billing" in out
    assert "charge.py:10" in out
    assert "exact" in out


def test_render_impact_no_producers():
    r = ImpactResult(symbol="ghost", producers=[], consumers=[])
    out = render_impact(r)
    assert "ghost" in out
    assert "No consumers" in out


def test_render_verify_columns_and_summary():
    rows = [
        VerifyRow(repo="billing", evidence="charge.py:10", confidence="exact",
                  contract="fail", tests="fail", state="fail",
                  reason="still references customer_id, which no producer exposes"),
        VerifyRow(repo="web", evidence="profile.py:10", confidence="exact",
                  contract="pass", tests="pass", state="pass",
                  reason="updated to account_id"),
        VerifyRow(repo="analytics", evidence="report.py:6", confidence="inferred",
                  contract="fail", tests="not_run", state="unknown",
                  reason="name match only; still references customer_id"),
    ]
    out = render_verify(rows)
    lines = out.splitlines()
    # header present
    assert "Consumer" in lines[0]
    assert "State" in lines[0]
    assert "Reason" in lines[0]
    # summary on last line with single-space separators
    summary = lines[-1]
    assert "pass=1" in summary
    assert "fail=1" in summary
    assert "not_run=0" in summary
    assert "unknown=1" in summary
    # single space between items (not double)
    assert "  " not in summary


def test_render_verify_empty_returns_empty():
    assert render_verify([]) == ""
