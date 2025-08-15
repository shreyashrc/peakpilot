from fastapi.testclient import TestClient

from api.main import app


def test_websocket_connection():
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_text("Is Triund open in July?")
        received_progress = False
        received_answer = False
        while True:
            try:
                msg = ws.receive_json()
            except Exception:
                break
            if msg.get("type") == "progress":
                received_progress = True
            if msg.get("type") == "answer":
                received_answer = True
                break
        assert received_progress and received_answer
