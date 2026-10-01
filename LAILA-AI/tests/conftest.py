import pytest
from fastapi.testclient import TestClient
from app.database import database as db
from app.main import app
from app.api import routes


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA", tmp_path)
    monkeypatch.setattr(routes, "DATA", tmp_path)
    with TestClient(app) as c:
        c.headers["X-Laila-Token"] = c.get("/api/session").json()["token"]
        yield c
