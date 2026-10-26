import pytest
from pathlib import Path
from atlas.verify import decide_state, run_test_cmd, verify
from atlas.scan import scan_repos
from atlas.db import open_db


@pytest.mark.parametrize("conf,contract,tests,expected", [
    ("inferred", "fail", "pass", "unknown"),
    ("inferred", "pass", "pass", "unknown"),
    ("exact", "fail", "not_run", "fail"),
    ("exact", "pass", "fail", "fail"),
    ("exact", "pass", "pass", "pass"),
    ("exact", "pass", "not_run", "not_run"),
    ("exact", "n/a", "not_run", "unknown"),
    ("exact", "pass", "unknown", "unknown"),
])
def test_decide_state(conf, contract, tests, expected):
    assert decide_state(conf, contract, tests) == expected


def test_run_test_cmd_pass_fail_timeout(tmp_path):
    assert run_test_cmd("exit 0", str(tmp_path), 5)[0] == "pass"
    state, out = run_test_cmd("echo boom; exit 3", str(tmp_path), 5)
    assert state == "fail" and "boom" in out
    state, out = run_test_cmd("sleep 5", str(tmp_path), 1)
    assert state == "unknown" and "timed out" in out


# ── fixtures for workspace tests ─────────────────────────────────────────────

_FASTAPI_STUB = """\
try:
    from fastapi import FastAPI
except ImportError:
    class FastAPI:
        def get(self, path): return lambda fn: fn
"""

def _write_ws(tmp_path, renamed=False):
    """Build a small multi-repo workspace and return open DB connection."""
    field = "account_id" if renamed else "customer_id"
    producer = tmp_path / "producer"
    producer.mkdir()
    (producer / "app.py").write_text(
        _FASTAPI_STUB +
        "app = FastAPI()\n\n"
        "@app.get(\"/u/{id}\")\n"
        "def g(id):\n"
        f"    return {{\"{field}\": 1}}\n"
    )

    con_a = tmp_path / "consumer_a"
    con_a.mkdir()
    (con_a / "a.py").write_text(
        "from urllib.request import urlopen\n"
        "B = \"http://x\"\n"
        "def f(i):\n"
        "    d = urlopen(f\"{B}/u/{i}\")\n"
        "    return d[\"customer_id\"]\n"
    )
    (con_a / "tests").mkdir()
    (con_a / "tests" / "test_a.py").write_text("def test_a():\n    assert False\n")

    con_b = tmp_path / "consumer_b"
    con_b.mkdir()
    (con_b / "b.py").write_text(
        "def f(row):\n"
        "    return row[\"customer_id\"]\n"
    )

    repos = [producer, con_a, con_b]

    if renamed:
        con_c = tmp_path / "consumer_c"
        con_c.mkdir()
        (con_c / "c.py").write_text(
            "from urllib.request import urlopen\n"
            "B = \"http://x\"\n"
            "def f(i):\n"
            "    d = urlopen(f\"{B}/u/{i}\")\n"
            "    return d[\"account_id\"]\n"
        )
        (con_c / "tests").mkdir()
        (con_c / "tests" / "test_c.py").write_text("def test_c():\n    assert True\n")
        repos.append(con_c)

    db = tmp_path / "a.db"
    scan_repos(repos, db)

    class WS:
        conn = open_db(db)

    return WS()


@pytest.fixture
def ws(tmp_path):
    return _write_ws(tmp_path, renamed=False)


@pytest.fixture
def ws_renamed(tmp_path):
    return _write_ws(tmp_path, renamed=True)


def test_verify_rows_on_fixture_workspace(ws):
    rows = {r.repo: r for r in verify(ws.conn, "customer_id")}
    assert rows["consumer_a"].state == "not_run"
    assert rows["consumer_a"].contract == "pass"
    assert rows["consumer_a"].tests == "not_run"
    assert rows["consumer_b"].state == "unknown"
    assert rows["consumer_b"].confidence == "inferred"


def test_verify_after_rename(ws_renamed):
    rows = {r.repo: r for r in verify(ws_renamed.conn, "customer_id",
                                       renamed_to="account_id",
                                       run_tests=True, timeout=30)}
    assert rows["consumer_a"].state == "fail" and rows["consumer_a"].contract == "fail"
    assert rows["consumer_c"].state == "pass"
    assert rows["consumer_c"].contract == "pass"
    assert rows["consumer_c"].tests == "pass"
    assert rows["consumer_b"].state == "unknown"


def test_verify_nobody_references(ws):
    assert verify(ws.conn, "ghost") == []
