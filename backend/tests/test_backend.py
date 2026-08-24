import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_root_or_health():
    """Verify backend root / chats endpoint is responsive."""
    response = client.get("/chats")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_chat_lifecycle():
    """Test creating, fetching, renaming, and deleting a chat session."""
    # 1. Create chat
    res_create = client.post("/chats", json={"title": "Pytest Test Chat"})
    assert res_create.status_code == 200
    chat_data = res_create.json()
    chat_id = chat_data["id"]
    assert chat_data["title"] == "Pytest Test Chat"

    # 2. Get chat detail
    res_get = client.get(f"/chats/{chat_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == chat_id

    # 3. Rename chat
    res_patch = client.patch(f"/chats/{chat_id}", json={"title": "Renamed Chat"})
    assert res_patch.status_code == 200
    assert res_patch.json()["title"] == "Renamed Chat"

    # 4. Delete chat
    res_del = client.delete(f"/chats/{chat_id}")
    assert res_del.status_code == 200

    # 5. Verify deleted
    res_check = client.get(f"/chats/{chat_id}")
    assert res_check.status_code == 404

def test_flashrank_reranker():
    """Verify FlashRank cross-encoder loads and ranks passages properly."""
    from flashrank import Ranker, RerankRequest
    ranker = Ranker(model_name="ms-marco-TinyBERT-L-2-v2")
    passages = [
        {"id": 1, "text": "Deep learning and LSTM for precipitation and rainfall forecasting."},
        {"id": 2, "text": "Recipe for chocolate cake and vanilla cupcakes."}
    ]
    req = RerankRequest(query="rainfall machine learning prediction", passages=passages)
    ranked = ranker.rerank(req)
    assert len(ranked) == 2
    assert ranked[0]["id"] == 1
