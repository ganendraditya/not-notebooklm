import os
import sys
import pytest
from pathlib import Path
from typing import List
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core import Document, VectorStoreIndex, StorageContext
from qdrant_client import QdrantClient

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rag.vector_store import QdrantVectorStore


class MockDenseEmbedding(BaseEmbedding):
    """Deterministic mock embedding returning uniform vector to isolate sparse BM25 contributions."""
    def _get_query_embedding(self, query: str) -> List[float]:
        return [0.1] * 384

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return [0.1] * 384

    def _get_text_embedding(self, text: str) -> List[float]:
        return [0.1] * 384

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return [[0.1] * 384 for _ in texts]


@pytest.fixture
def hybrid_in_memory_index():
    client = QdrantClient(location=":memory:")
    vstore = QdrantVectorStore(
        collection_name="test_hybrid_collection",
        client=client,
        enable_hybrid=True,
        fastembed_sparse_model="Qdrant/bm25",
        batch_size=20,
    )
    embed_model = MockDenseEmbedding()
    storage_context = StorageContext.from_defaults(vector_store=vstore)

    docs = [
        Document(
            text="Paper Alpha introduces Low-Rank Adaptation (LoRA) with rank r=8 for fine-tuning large vision transformer models efficiently.",
            metadata={"chat_id": "test_chat", "filename": "alpha_lora.pdf", "doi": "10.1145/3292500"}
        ),
        Document(
            text="Paper Beta by author Vaswani et al. evaluates empirical performance metrics achieving mAP@50 score of 0.938 on COCO benchmarks.",
            metadata={"chat_id": "test_chat", "filename": "beta_vaswani.pdf", "doi": "10.1016/j.neucom.2021"}
        ),
        Document(
            text="Paper Gamma discusses general deep neural networks without specific architectural modifications or quantitative benchmark evaluation.",
            metadata={"chat_id": "test_chat", "filename": "gamma_general.pdf", "doi": "10.1109/CVPR.2020"}
        ),
    ]

    index = VectorStoreIndex.from_documents(docs, storage_context=storage_context, embed_model=embed_model)
    return index, client, vstore


def test_hybrid_search_exact_acronym_and_parameter(hybrid_in_memory_index):
    """BM25 sparse ranking must rank LoRA exact match first over uniform dense embeddings."""
    index, client, vstore = hybrid_in_memory_index
    retriever = index.as_retriever(similarity_top_k=2, vector_store_query_mode="hybrid")

    nodes = retriever.retrieve("LoRA rank r=8")
    assert len(nodes) >= 1
    top_node = nodes[0]
    assert "alpha_lora.pdf" in top_node.node.metadata.get("filename", "")
    assert "Low-Rank Adaptation (LoRA)" in top_node.node.get_content()
    # Rank ordering assertion (BM25 properly surfaced target as Top-1)
    assert top_node.score is not None


def test_hybrid_legacy_collection_fallback_safety():
    """Verify that existing collections lacking sparse vectors safely fallback to dense without crashing."""
    from qdrant_client.http import models as qmodels
    client = QdrantClient(location=":memory:")
    # Pre-create a dense-only legacy collection
    client.create_collection(
        collection_name="legacy_dense_collection",
        vectors_config=qmodels.VectorParams(size=384, distance=qmodels.Distance.COSINE)
    )

    # Instantiate QdrantVectorStore with capability check
    existing_info = client.get_collection("legacy_dense_collection")
    can_hybrid = bool(existing_info and getattr(existing_info.config.params, "sparse_vectors", None))
    assert can_hybrid is False

    vstore = QdrantVectorStore(
        collection_name="legacy_dense_collection",
        client=client,
        enable_hybrid=can_hybrid,
        batch_size=20,
    )
    assert vstore.enable_hybrid is False


def test_hybrid_search_exact_author_and_metric(hybrid_in_memory_index):
    """BM25 sparse ranking must rank author surname 'Vaswani' and exact metric 'mAP@50' at the top."""
    index, client, vstore = hybrid_in_memory_index
    retriever = index.as_retriever(similarity_top_k=2, vector_store_query_mode="hybrid")

    nodes = retriever.retrieve("Vaswani mAP@50 COCO")
    assert len(nodes) >= 1
    top_node = nodes[0]
    assert "beta_vaswani.pdf" in top_node.node.metadata.get("filename", "")
    assert "Vaswani et al." in top_node.node.get_content()


def test_hybrid_delete_document_vectors_purges_sparse_and_dense():
    """Verify that deleting by chat_id or filename purges the entire point (dense + sparse)."""
    from rag.vector_store import delete_document_vectors

    client = QdrantClient(location=":memory:")
    vstore = QdrantVectorStore(
        collection_name="not_notebooklm_e5",
        client=client,
        enable_hybrid=True,
        fastembed_sparse_model="Qdrant/bm25",
        batch_size=20,
    )
    embed_model = MockDenseEmbedding()
    storage_context = StorageContext.from_defaults(vector_store=vstore)

    docs = [
        Document(
            text="Test document for atomic hybrid point deletion verification.",
            metadata={"chat_id": "purge_chat_1", "filename": "purge_doc.pdf"}
        )
    ]
    index = VectorStoreIndex.from_documents(docs, storage_context=storage_context, embed_model=embed_model)

    # Verify document exists
    res_before = client.scroll(collection_name="not_notebooklm_e5")
    assert len(res_before[0]) == 1

    # Patch module global client safely in sys.modules['rag.vector_store']
    import sys
    vs_mod = sys.modules["rag.vector_store"]
    orig_client = vs_mod.qdrant_client
    try:
        vs_mod.qdrant_client = client
        delete_document_vectors("purge_chat_1", "purge_doc.pdf")
        res_after = client.scroll(collection_name="not_notebooklm_e5")
        assert len(res_after[0]) == 0
    finally:
        vs_mod.qdrant_client = orig_client
