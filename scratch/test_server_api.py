import sys
import os

avatar_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if avatar_root not in sys.path:
    sys.path.insert(0, avatar_root)

from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

def test_endpoints():
    print("Testing /api/config...")
    res = client.get("/api/config")
    print("Status:", res.status_code, res.json())

    print("\nTesting /api/chat with simple greeting...")
    res = client.post("/api/chat", json={"message": "Hola"})
    print("Status:", res.status_code, res.json())

    print("\nTesting /api/chat with tool command...")
    res = client.post("/api/chat", json={"message": "Lista el contenido del directorio actual"})
    print("Status:", res.status_code, res.json())

if __name__ == "__main__":
    test_endpoints()
