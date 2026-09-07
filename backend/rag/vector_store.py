import os
import logging
from typing import Optional
from dotenv import load_dotenv

from llama_index.vector_stores.qdrant import QdrantVectorStore as _BaseQdrantVectorStore
from qdrant_client import QdrantClient


class QdrantVectorStore(_BaseQdrantVectorStore):
    """Compat shim for llama-index-vector-stores-qdrant 0.1.4 on pydantic v2.

    The upstream class declares `path`/`url`/`api_key` as `Optional[...]`
    without defaults (which pydantic v2 treats as REQUIRED), but its
    `__init__` never forwards `path` to `super().__init__()`, so plain
    instantiation raises `ValidationError: path Field required`.
    Redeclaring the fields with defaults fixes validation without
    changing runtime behavior.
    """

    path: Optional[str] = None
    url: Optional[str] = None
    api_key: Optional[str] = None

from llama_index.embeddings.gemini import GeminiEmbedding
try:
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
except Exception:
    HuggingFaceEmbedding = None

load_dotenv()
logger = logging.getLogger("uvicorn.error")

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "qdrant_data"))
os.makedirs(QDRANT_PATH, exist_ok=True)

# Setup Qdrant Client (Supports Remote Server / Docker or Local Disk fallback)
if QDRANT_URL:
    try:
        qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        logger.info(f"[Qdrant] Connected to remote server at {QDRANT_URL}")
    except Exception as e:
        logger.warning(f"[Qdrant] Failed connecting to remote URL {QDRANT_URL}: {e}. Falling back to disk.")
        qdrant_client = QdrantClient(path=QDRANT_PATH, force_disable_check_same_thread=True)
else:
    try:
        qdrant_client = QdrantClient(path=QDRANT_PATH, force_disable_check_same_thread=True)
    except Exception:
        try:
            qdrant_client = QdrantClient(path=QDRANT_PATH)
        except Exception:
            qdrant_client = QdrantClient(location=":memory:")


def init_embedding_and_vector_store():
    """Initializes embeddings (Local BGE or Gemini) and associates with Qdrant."""
    env_provider = os.getenv("EMBEDDING_PROVIDER", "local").lower()
    gemini_key = os.getenv("GEMINI_API_KEY")

    if env_provider == "gemini" and gemini_key and not gemini_key.startswith("your_"):
        try:
            embed_model = GeminiEmbedding(model_name="models/gemini-embedding-2", api_key=gemini_key)
            vstore = QdrantVectorStore(collection_name="not_notebooklm_gemini", client=qdrant_client, enable_hybrid=False, batch_size=20)
            return embed_model, vstore
        except Exception as e:
            logger.warning(f"[RAG Engine] Gemini Embedding initialization failed ({e}), falling back to local BGE embeddings.")

    # Default Local Offline Embeddings
    if HuggingFaceEmbedding is not None:
        try:
            embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
            vstore = QdrantVectorStore(collection_name="not_notebooklm_bge", client=qdrant_client, enable_hybrid=False, batch_size=20)
            return embed_model, vstore
        except Exception as e:
            logger.warning(f"[RAG Engine] HuggingFace Embedding loading failed: {e}")

    # Ultimate fallback to Gemini
    embed_model = GeminiEmbedding(model_name="models/gemini-embedding-2", api_key=gemini_key)
    vstore = QdrantVectorStore(collection_name="not_notebooklm", client=qdrant_client, enable_hybrid=False, batch_size=20)
    return embed_model, vstore


def delete_document_vectors(chat_id: str, doc_filename: Optional[str] = None):
    """Purges points from vector store by chat_id and optionally by doc_filename.
    Abstracted interface to ensure reversibility if vector db provider changes."""
    try:
        from qdrant_client.http import models as qmodels
        conditions = [
            qmodels.FieldCondition(key="chat_id", match=qmodels.MatchValue(value=chat_id))
        ]
        if doc_filename:
            # Support both 'filename' (standard across engine.py) and 'file_name'
            filter_obj = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(key="chat_id", match=qmodels.MatchValue(value=chat_id)),
                    qmodels.Filter(
                        should=[
                            qmodels.FieldCondition(key="filename", match=qmodels.MatchValue(value=doc_filename)),
                            qmodels.FieldCondition(key="file_name", match=qmodels.MatchValue(value=doc_filename))
                        ]
                    )
                ]
            )
        else:
            filter_obj = qmodels.Filter(must=conditions)
        
        collections = []
        try:
            collections_response = qdrant_client.get_collections()
            collections = [c.name for c in collections_response.collections]
        except Exception as e:
            logger.warning(f"[Qdrant] Failed listing collections for deletion: {e}")
            collections = ["not_notebooklm_bge", "not_notebooklm_gemini", "not_notebooklm"]
            
        for coll in collections:
            try:
                qdrant_client.delete(collection_name=coll, points_selector=filter_obj)
            except Exception as ce:
                logger.debug(f"Could not delete from {coll}: {ce}")
    except Exception as e:
        logger.error(f"[Qdrant Cleanup Error] Failed to delete vectors for chat_id={chat_id}: {str(e)}")

# Initialize singletons
embed_model, vector_store = init_embedding_and_vector_store()

# Backward-compatibility alias
delete_qdrant_vectors = delete_document_vectors
