import os
import logging
from typing import Optional
from dotenv import load_dotenv

from llama_index.vector_stores.qdrant import QdrantVectorStore as _BaseQdrantVectorStore
import qdrant_client
from qdrant_client import QdrantClient

# Compatibility shim for qdrant-client >= 1.14 where .search was replaced by .query_points
if not hasattr(QdrantClient, "search"):
    def _compat_search(self, collection_name, query_vector, query_filter=None, search_params=None, limit=10, offset=None, with_payload=True, with_vectors=False, score_threshold=None, **kwargs):
        res = self.query_points(
            collection_name=collection_name,
            query=query_vector,
            query_filter=query_filter,
            search_params=search_params,
            limit=limit,
            offset=offset,
            with_payload=with_payload,
            with_vectors=with_vectors,
            score_threshold=score_threshold,
            **kwargs
        )
        return res.points
    QdrantClient.search = _compat_search

if hasattr(qdrant_client, "AsyncQdrantClient") and not hasattr(qdrant_client.AsyncQdrantClient, "search"):
    async def _compat_asearch(self, collection_name, query_vector, query_filter=None, search_params=None, limit=10, offset=None, with_payload=True, with_vectors=False, score_threshold=None, **kwargs):
        res = await self.query_points(
            collection_name=collection_name,
            query=query_vector,
            query_filter=query_filter,
            search_params=search_params,
            limit=limit,
            offset=offset,
            with_payload=with_payload,
            with_vectors=with_vectors,
            score_threshold=score_threshold,
            **kwargs
        )
        return res.points
    qdrant_client.AsyncQdrantClient.search = _compat_asearch


class QdrantVectorStore(_BaseQdrantVectorStore):
    """Compat shim for llama-index-vector-stores-qdrant 0.1.4 on pydantic v2.

    The upstream class declares `path`/`url`/`api_key` as `Optional[...]`
    without defaults (which pydantic v2 treats as REQUIRED), but its
    `__init__` never forwards `path` to `super().__init__()`, so plain
    instantiation raises `ValidationError: path Field required`.
    Redeclaring the fields with defaults fixes validation without
    changing runtime behavior. Also ensures private `_client` and collection state are preserved.
    """

    path: Optional[str] = None
    url: Optional[str] = None
    api_key: Optional[str] = None

    def __init__(self, *args, **kwargs):
        client = kwargs.get("client")
        aclient = kwargs.get("aclient")
        super().__init__(*args, **kwargs)
        if client is not None:
            self._client = client
            try:
                self._collection_initialized = self._collection_exists(self.collection_name)
            except Exception:
                self._collection_initialized = False
        if aclient is not None:
            self._aclient = aclient

try:
    from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
except ImportError:
    try:
        from llama_index.embeddings.gemini import GeminiEmbedding as GoogleGenAIEmbedding
    except ImportError:
        GoogleGenAIEmbedding = None

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
        qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=5)
        qdrant_client.get_collections()
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
    """Initializes embeddings (Local Multilingual E5 or Google GenAI / Gemini) and associates with Qdrant."""
    env_provider = os.getenv("EMBEDDING_PROVIDER", "local").lower()
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    embedding_model = os.getenv("GEMINI_EMBEDDING_MODEL", "models/text-embedding-004")

    if env_provider in ("gemini", "google") and gemini_key and not gemini_key.startswith("your_"):
        if GoogleGenAIEmbedding is not None:
            try:
                embed_model = GoogleGenAIEmbedding(model_name=embedding_model, api_key=gemini_key)
                vstore = QdrantVectorStore(collection_name="not_notebooklm_gemini", client=qdrant_client, enable_hybrid=False, batch_size=20)
                return embed_model, vstore
            except Exception as e:
                logger.warning(f"[RAG Engine] Google GenAI Embedding initialization failed ({e}), falling back to local Multilingual E5 embeddings.")

    # Default Local Offline Embeddings (Multilingual 93+ languages)
    if HuggingFaceEmbedding is not None:
        try:
            embed_model = HuggingFaceEmbedding(model_name="intfloat/multilingual-e5-small")
            vstore = QdrantVectorStore(collection_name="not_notebooklm_e5", client=qdrant_client, enable_hybrid=False, batch_size=20)
            return embed_model, vstore
        except Exception as e:
            logger.warning(f"[RAG Engine] HuggingFace Embedding loading failed: {e}")

    # Ultimate fallback to Google GenAI / Gemini
    if GoogleGenAIEmbedding is not None and gemini_key and not gemini_key.startswith("your_"):
        embed_model = GoogleGenAIEmbedding(model_name=embedding_model, api_key=gemini_key)
        vstore = QdrantVectorStore(collection_name="not_notebooklm", client=qdrant_client, enable_hybrid=False, batch_size=20)
        return embed_model, vstore

    raise RuntimeError("No embedding provider available or valid API key configured. Please install llama-index-embeddings-huggingface or set GEMINI_API_KEY.")


def delete_document_vectors(chat_id: str, doc_filename: Optional[str] = None):
    """Purges points from vector store by chat_id and optionally by doc_filename.
    Abstracted interface to ensure reversibility if vector db provider changes."""
    try:
        from qdrant_client.http import models as qmodels
        conditions = [
            qmodels.FieldCondition(key="chat_id", match=qmodels.MatchValue(value=chat_id))
        ]
        if doc_filename:
            # Support both 'filename' (standard across engine.py) and 'file_name', plus legacy prefixed names
            prefixed_name = f"{chat_id}_{doc_filename}"
            filter_obj = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(key="chat_id", match=qmodels.MatchValue(value=chat_id)),
                    qmodels.Filter(
                        should=[
                            qmodels.FieldCondition(key="filename", match=qmodels.MatchValue(value=doc_filename)),
                            qmodels.FieldCondition(key="file_name", match=qmodels.MatchValue(value=doc_filename)),
                            qmodels.FieldCondition(key="filename", match=qmodels.MatchValue(value=prefixed_name)),
                            qmodels.FieldCondition(key="file_name", match=qmodels.MatchValue(value=prefixed_name)),
                        ]
                    )
                ]
            )
        else:
            filter_obj = qmodels.Filter(must=conditions)
        
        collections = []
        try:
            collections_response = qdrant_client.get_collections()
            collections = [c.name for c in collections_response.collections if c.name.startswith("not_notebooklm")]
        except Exception as e:
            logger.warning(f"[Qdrant] Failed listing collections for deletion: {e}")
            collections = ["not_notebooklm_e5", "not_notebooklm_bge", "not_notebooklm_gemini", "not_notebooklm"]
            
        for coll in collections:
            try:
                qdrant_client.delete(collection_name=coll, points_selector=filter_obj)
            except Exception as ce:
                logger.debug(f"Could not delete from {coll}: {ce}")
    except Exception as e:
        logger.error(f"[Qdrant Cleanup Error] Failed to delete vectors for chat_id={chat_id}: {str(e)}")

# Initialize singletons
embed_model, vector_store = init_embedding_and_vector_store()
try:
    from llama_index.core import Settings
    Settings.embed_model = embed_model
except Exception:
    pass

# Backward-compatibility alias
delete_qdrant_vectors = delete_document_vectors

_flashrank_ranker = None

def get_flashrank_ranker(model_name: str = "ms-marco-TinyBERT-L-2-v2"):
    """Singleton getter for FlashRank cross-encoder to prevent disk reload per query."""
    global _flashrank_ranker
    if _flashrank_ranker is None:
        try:
            from flashrank import Ranker
            _flashrank_ranker = Ranker(model_name=model_name)
        except Exception as e:
            logger.warning(f"[FlashRank] Failed to initialize Ranker ({model_name}): {e}")
            return None
    return _flashrank_ranker


def ingest_documents_batch(doc_items: list) -> bool:
    """Single Source of Truth: Batch ingests multiple (text, filename, chat_id) into Qdrant with section-aware chunks."""
    if not doc_items:
        return True
    from llama_index.core import Document, VectorStoreIndex, StorageContext
    from .parsers import split_markdown_into_academic_sections

    docs = []
    for text, filename, chat_id in doc_items:
        sections = split_markdown_into_academic_sections(text, filename=filename, embed_model=embed_model)
        for sec in sections:
            docs.append(
                Document(
                    text=sec.get("text", text),
                    metadata={
                        "chat_id": chat_id,
                        "source_type": "file",
                        "filename": filename,
                        "section": sec.get("section", "Overview"),
                        "breadcrumb": sec.get("breadcrumb", "Overview"),
                        "canonical_section": sec.get("canonical_section", "general"),
                    }
                )
            )
    if not docs:
        docs = [
            Document(
                text=text,
                metadata={"chat_id": chat_id, "source_type": "file", "filename": filename}
            )
            for text, filename, chat_id in doc_items
        ]
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    VectorStoreIndex.from_documents(docs, storage_context=storage_context, embed_model=embed_model, show_progress=False)
    return True


def ingest_document_text(text: str, filename: str, chat_id: str) -> bool:
    """Ingests text into the vector database under a specific chat_id with section-aware chunking."""
    return ingest_documents_batch([(text, filename, chat_id)])


def ingest_document(file_path: str, chat_id: str, filename: Optional[str] = None) -> bool:
    """Parses a multi-format document and ingests it into Qdrant."""
    from .parsers import parse_document_to_markdown
    fn = filename or os.path.basename(file_path)
    md_text = parse_document_to_markdown(file_path)
    return ingest_document_text(md_text, fn, chat_id)

