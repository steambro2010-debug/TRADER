import requests

BASE_URL = "http://127.0.0.1:8000"


def get(path: str):
    resp = requests.get(f"{BASE_URL}{path}", timeout=5)
    resp.raise_for_status()
    return resp.json()


def post(path: str, payload: dict):
    resp = requests.post(f"{BASE_URL}{path}", json=payload, timeout=5)
    resp.raise_for_status()
    return resp.json()
