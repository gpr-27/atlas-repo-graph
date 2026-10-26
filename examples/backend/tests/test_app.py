import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from app import get_user

def test_get_user_has_customer_id():
    assert get_user(1)["customer_id"] == "C1"
