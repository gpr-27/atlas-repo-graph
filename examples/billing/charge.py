import json
from urllib.request import urlopen

BASE = "http://localhost:8000"


def charge_user(user_id: int, amount: int) -> dict:
    with urlopen(f"{BASE}/users/{user_id}") as resp:
        data = json.load(resp)
    return {"customer": data["customer_id"], "amount": amount}
