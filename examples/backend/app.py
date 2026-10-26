try:
    from fastapi import FastAPI
except ImportError:  # demo runs without FastAPI installed
    class FastAPI:
        def get(self, path):
            return lambda fn: fn

app = FastAPI()


@app.get("/users/{user_id}")
def get_user(user_id: int):
    return {"id": user_id, "customer_id": f"C{user_id}", "email": f"user{user_id}@example.com"}
