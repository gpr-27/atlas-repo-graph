import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import profile
from contract import fake_urlopen


def test_profile_label(monkeypatch):
    monkeypatch.setattr(profile, "urlopen", fake_urlopen)
    assert profile.profile_label(1).startswith("C1")
