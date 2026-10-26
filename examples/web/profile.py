import json
from urllib.request import urlopen

BASE = "http://localhost:8000"


def profile_label(user_id: int) -> str:
    with urlopen(f"{BASE}/users/{user_id}") as resp:
        user = json.load(resp)
    return f"{user['customer_id']} <{user['email']}>"
