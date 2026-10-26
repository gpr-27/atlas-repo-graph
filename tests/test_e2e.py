"""End-to-end test: copy the examples workspace, run demo sequence, assert states."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from atlas.cli import main

EXAMPLES = Path(__file__).parent.parent / "examples"


@pytest.fixture()
def workspace(tmp_path):
    """Copy examples/ into tmp_path so each test run is isolated."""
    dest = tmp_path / "examples"
    shutil.copytree(EXAMPLES, dest, dirs_exist_ok=True)
    return dest


def _scan(ws: Path, db: str):
    return main(["scan",
                 str(ws / "backend"), str(ws / "billing"),
                 str(ws / "web"), str(ws / "analytics"),
                 "--db", db])


def test_e2e_impact_has_three_consumers(workspace, tmp_path, capsys):
    db = str(tmp_path / "a.db")
    assert _scan(workspace, db) == 0
    capsys.readouterr()
    assert main(["impact", "customer_id", "--json", "--db", db]) == 0
    data = json.loads(capsys.readouterr().out)
    consumer_repos = {c["repo"] for c in data["consumers"]}
    assert consumer_repos >= {"billing", "web", "analytics"}


def test_e2e_verify_states_after_rename(workspace, tmp_path, capsys):
    db = str(tmp_path / "b.db")
    assert _scan(workspace, db) == 0

    # Apply the rename using the workspace's own copy of the script
    subprocess.run(
        ["bash", str(workspace / "apply_rename.sh")],
        check=True,
    )
    # Re-scan after rename
    assert _scan(workspace, db) == 0

    capsys.readouterr()
    rc = main(["verify", "customer_id", "--renamed-to", "account_id",
               "--run-tests", "--json", "--db", db])
    assert rc == 2  # at least one fail
    rows = {r["repo"]: r for r in json.loads(capsys.readouterr().out)}
    assert rows["analytics"]["state"] == "unknown"
    assert rows["billing"]["state"] == "fail"
    assert rows["web"]["state"] == "pass"


def test_e2e_verify_no_run_tests(workspace, tmp_path, capsys):
    db = str(tmp_path / "c.db")
    assert _scan(workspace, db) == 0
    subprocess.run(["bash", str(workspace / "apply_rename.sh")], check=True)
    assert _scan(workspace, db) == 0
    capsys.readouterr()
    main(["verify", "customer_id", "--renamed-to", "account_id", "--json", "--db", db])
    rows = {r["repo"]: r for r in json.loads(capsys.readouterr().out)}
    assert rows["web"]["state"] == "not_run"
