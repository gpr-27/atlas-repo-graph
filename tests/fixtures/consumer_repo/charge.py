import requests
BASE = "http://localhost:8000"

def charge_user(user_id, amount):
    resp = requests.get(f"{BASE}/users/{user_id}")
    data = resp.json()
    name = data.get("email")
    return {"customer": data["customer_id"], "amount": amount, "email": name}

def ping():
    return requests.get("http://localhost:8000/health/").status_code
