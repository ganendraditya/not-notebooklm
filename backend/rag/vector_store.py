import os
import asyncio
import logging
import threading
from typing import Optional, List, Any
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
    from fastembed import TextEmbedding as FastEmbedTextEmbedding
except ImportError:
    FastEmbedTextEmbedding = None

try:
    from llama_index.core.embeddings import BaseEmbedding
except ImportError:
    BaseEmbedding = object  # Fallback for type annotation safety

class FastEmbedDenseEmbedding(BaseEmbedding):
    """Native ONNX-powered dense multilingual embedding provider using FastEmbed.
    Zero-PyTorch footprint, sub-millisecond CPU latency, and ~220MB model footprint."""

    model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    _engine: Any = None

    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", **kwargs):
        super().__init__(model_name=model_name, **kwargs)
        if FastEmbedTextEmbedding is None:
            raise RuntimeError("fastembed package is not installed. Please install fastembed>=0.8.0.")
        self._engine = FastEmbedTextEmbedding(model_name=model_name)

    def _get_query_embedding(self, query: str) -> List[float]:
        return list(self._engine.embed([query]))[0].tolist()

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return await asyncio.to_thread(self._get_query_embedding, query)

    def _get_text_embedding(self, text: str) -> List[float]:
        return list(self._engine.embed([text]))[0].tolist()

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return await asyncio.to_thread(self._get_text_embedding, text)

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return [vec.tolist() for vec in self._engine.embed(texts)]

    async def _aget_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return await asyncio.to_thread(self._get_text_embeddings, texts)

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
    """Initializes embeddings (Local FastEmbed Multilingual ONNX or Google GenAI / Gemini) and associates with Qdrant."""
    env_provider = os.getenv("EMBEDDING_PROVIDER", "local").lower()
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    embedding_model = os.getenv("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-001")

    # Helper to instantiate QdrantVectorStore with hybrid BM25 and schema capability detection
    def _create_hybrid_qdrant_store(collection_name: str) -> QdrantVectorStore:
        can_enable_hybrid = True
        try:
            # Check if collection already exists on disk/remote without sparse vectors schema
            existing_info = qdrant_client.get_collection(collection_name)
            if existing_info and not getattr(existing_info.config.params, "sparse_vectors", None):
                logger.warning(
                    f"[VectorStore] Existing collection '{collection_name}' lacks sparse vectors schema. "
                    "Safely running in dense-only mode to prevent ValueError crashes."
                )
                can_enable_hybrid = False
        except Exception:
            # Collection does not exist yet; fresh creation will configure sparse vectors automatically
            can_enable_hybrid = True

        try:
            return QdrantVectorStore(
                collection_name=collection_name,
                client=qdrant_client,
                enable_hybrid=can_enable_hybrid,
                fastembed_sparse_model="Qdrant/bm25" if can_enable_hybrid else None,
                batch_size=20,
            )
        except Exception as e:
            logger.warning(
                f"[VectorStore] Hybrid initialization failed for {collection_name} ({e}). "
                "Falling back to dense-only vector store."
            )
            return QdrantVectorStore(
                collection_name=collection_name,
                client=qdrant_client,
                enable_hybrid=False,
                batch_size=20,
            )

    def _get_gemini_collection_name(model_name: str) -> str:
        """Determines Qdrant collection name based on Gemini model dimensionality (3072 dim vs 768 dim)."""
        # gemini-embedding-001 and gemini-embedding-2-preview output 3072-dimensional vectors
        if "001" in model_name or "preview" in model_name:
            return "not_notebooklm_gemini_3072"
        return "not_notebooklm_gemini"

    # 1. Cloud Provider: Google Gemini GenAI Embedding
    if env_provider in ("gemini", "google") and gemini_key and not gemini_key.startswith("your_"):
        if GoogleGenAIEmbedding is not None:
            try:
                embed_model = GoogleGenAIEmbedding(model_name=embedding_model, api_key=gemini_key)
                target_col = _get_gemini_collection_name(embedding_model)
                vstore = _create_hybrid_qdrant_store(target_col)
                return embed_model, vstore
            except Exception as e:
                logger.warning(f"[RAG Engine] Google GenAI Embedding initialization failed ({e}), falling back to local FastEmbed ONNX embeddings.")

    # 2. Primary Local-First Provider: FastEmbed Multilingual ONNX (Zero-PyTorch, ~220MB, 384 dimensions)
    if FastEmbedTextEmbedding is not None:
        try:
            embed_model = FastEmbedDenseEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
            target_col = "not_notebooklm_fastembed"
            try:
                existing_cols = [c.name for c in qdrant_client.get_collections().collections]
                if "not_notebooklm_e5" in existing_cols:
                    logger.info("[RAG Engine] Legacy 'not_notebooklm_e5' collection detected. Using isolated 'not_notebooklm_fastembed' collection to prevent vector space collision.")
            except Exception:
                pass

            vstore = _create_hybrid_qdrant_store(target_col)
            logger.info(f"[RAG Engine] FastEmbed Multilingual ONNX initialized successfully (Collection: {target_col}).")
            return embed_model, vstore
        except Exception as e:
            logger.warning(f"[RAG Engine] FastEmbed dense embedding loading failed: {e}")

    # 3. Secondary Local Provider Fallback: Legacy HuggingFace (if installed)
    if HuggingFaceEmbedding is not None:
        try:
            embed_model = HuggingFaceEmbedding(model_name="intfloat/multilingual-e5-small")
            vstore = _create_hybrid_qdrant_store("not_notebooklm_e5")
            return embed_model, vstore
        except Exception as e:
            logger.warning(f"[RAG Engine] HuggingFace Embedding loading failed: {e}")

    # 4. Ultimate fallback to Google GenAI / Gemini
    if GoogleGenAIEmbedding is not None and gemini_key and not gemini_key.startswith("your_"):
        embed_model = GoogleGenAIEmbedding(model_name=embedding_model, api_key=gemini_key)
        target_col = _get_gemini_collection_name(embedding_model)
        vstore = _create_hybrid_qdrant_store(target_col)
        return embed_model, vstore

    raise RuntimeError("No embedding provider available or valid API key configured. FastEmbed or Gemini API key is required.")


def delete_document_vectors(chat_id: str, doc_filename: Optional[str] = None):
    """Purges points from vector store by chat_id and optionally by doc_filename.
    Abstracted interface to ensure reversibility if vector db provider changes."""
    try:
        from qdrant_client.http import models as qmodels
        conditions = [
            qmodels.FieldCondition(key="chat_id", match=qmodels.MatchValue(value=chat_id))
        ]
        if doc_filename:
            # Normalize filename: strip existing chat_id prefix to prevent double-prefixing
            bare_filename = doc_filename
            if chat_id and bare_filename.startswith(f"{chat_id}_"):
                bare_filename = bare_filename[len(chat_id) + 1:]
            prefixed_name = f"{chat_id}_{bare_filename}"

            # Sweep both current and pre-upgrade counterpart extensions (e.g. .pdf <-> .txt, .bib, .ris, .md)
            candidate_names = {bare_filename, prefixed_name}
            if bare_filename.lower().endswith(".pdf"):
                base = bare_filename[:-4]
                pref_base = prefixed_name[:-4]
                for ext in (".txt", ".bib", ".bibtex", ".ris", ".md"):
                    candidate_names.add(f"{base}{ext}")
                    candidate_names.add(f"{pref_base}{ext}")
            elif bare_filename.lower().endswith((".txt", ".bib", ".bibtex", ".ris", ".md")):
                ext_len = len(os.path.splitext(bare_filename)[1])
                base = bare_filename[:-ext_len] if ext_len > 0 else bare_filename
                pref_base = prefixed_name[:-ext_len] if ext_len > 0 else prefixed_name
                candidate_names.add(f"{base}.pdf")
                candidate_names.add(f"{pref_base}.pdf")

            should_conditions = []
            for c_name in candidate_names:
                should_conditions.append(qmodels.FieldCondition(key="filename", match=qmodels.MatchValue(value=c_name)))
                should_conditions.append(qmodels.FieldCondition(key="file_name", match=qmodels.MatchValue(value=c_name)))

            filter_obj = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(key="chat_id", match=qmodels.MatchValue(value=chat_id)),
                    qmodels.Filter(should=should_conditions)
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
            collections = [
                "not_notebooklm_fastembed",
                "not_notebooklm_gemini_3072",
                "not_notebooklm_e5",
                "not_notebooklm_bge",
                "not_notebooklm_gemini",
                "not_notebooklm",
            ]
            
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
_flashrank_lock = threading.Lock()

def get_flashrank_ranker(model_name: str = "ms-marco-TinyBERT-L-2-v2"):
    """Singleton getter for FlashRank cross-encoder to prevent disk reload per query (thread-safe)."""
    global _flashrank_ranker
    if _flashrank_ranker is None:
        with _flashrank_lock:
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

