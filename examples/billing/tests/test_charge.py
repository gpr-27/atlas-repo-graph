import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import charge
from contract import fake_urlopen


def test_charge_uses_backend_contract(monkeypatch):
    monkeypatch.setattr(charge, "urlopen", fake_urlopen)
    assert charge.charge_user(1, 500)["customer"] == "C1"
