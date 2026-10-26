from fastapi import FastAPI, APIRouter
from flask import jsonify
app = FastAPI()
router = APIRouter()

@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {"id": user_id, "customer_id": f"C{user_id}", "email": "a@b.c"}

@router.post("/orders")
def create_order():
    return jsonify({"order_id": 1})

@app.route("/legacy/<int:id>", methods=["GET", "DELETE"])
def legacy(id):
    return {"ok": True}

@app.get("/opaque")
def opaque():
    user = load()
    return user