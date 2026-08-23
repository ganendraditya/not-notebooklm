import pytest
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, Base, engine

# Setup test DB
Base.metadata.create_all(bind=engine)

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_read_main(client):
    response = client.get("/")
    assert response.status_code == 200

def test_create_chat(client):
    response = client.post("/chats", json={"title": "Test Chat"})
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["title"] == "Test Chat"

def test_get_chats(client):
    response = client.get("/chats")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
