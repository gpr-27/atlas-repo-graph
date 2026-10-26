from pathlib import Path
from atlas.cli import main
FIX = Path(__file__).parent / "fixtures"

def test_scan_and_status(tmp_path, capsys):
    db = str(tmp_path / "a.db")
    assert main(["scan", str(FIX / "routes_repo"), str(FIX / "consumer_repo"), "--db", db]) == 0
    assert main(["status", "--db", db]) == 0
    out = capsys.readouterr().out
    assert "routes_repo" in out and "consumer_repo" in out and "endpoint" in out

def test_status_missing_db_returns_1(tmp_path, capsys):
    assert main(["status", "--db", str(tmp_path / "none.db")]) == 1
    assert "not found" in capsys.readouterr().err.lower()
