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

def test_clean_doi():
    from helpers import clean_doi
    assert clean_doi("https://doi.org/10.1234/5678") == "10.1234/5678"
    assert clean_doi("doi: 10.1000/xyz123 ") == "10.1000/xyz123"
    assert clean_doi("**10.999/test**") == "10.999/test"
    assert clean_doi(None) == ""

def test_is_authentic_pdf_bytes():
    from pdf_exporter import is_authentic_pdf_bytes
    # Too small
    assert is_authentic_pdf_bytes(b"%PDF-1.4...", min_size=50) == False
    
    # Valid
    valid_pdf = b"%PDF-1.4" + b"0" * 1050
    assert is_authentic_pdf_bytes(valid_pdf, min_size=1024) == True
    
    # Invalid magic
    invalid_pdf = b"HTML" + b"0" * 1050
    assert is_authentic_pdf_bytes(invalid_pdf, min_size=1024) == False
    
    # Fake synthetic PDF flag
    fake_pdf = b"%PDF-1.4" + b"0" * 500 + b"NOTBOOKLM SCHOLARLY ARCHIVE" + b"0" * 500
    assert is_authentic_pdf_bytes(fake_pdf, min_size=1024) == False
