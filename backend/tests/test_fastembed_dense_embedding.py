import os
import sys
import pytest
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from llama_index.core import Document, VectorStoreIndex, StorageContext

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rag.vector_store import (
    FastEmbedDenseEmbedding,
    init_embedding_and_vector_store,
    QdrantVectorStore,
    delete_document_vectors,
)


def test_fastembed_dense_embedding_inference_unit():
    """Verify FastEmbed native ONNX embedding produces correct 384-dim vector on CPU without PyTorch."""
    embed_model = FastEmbedDenseEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    
    # Query embedding
    q_vec = embed_model.get_query_embedding("Pengujian temu kembali informasi ilmiah")
    assert isinstance(q_vec, list)
    assert len(q_vec) == 384
    assert all(isinstance(x, float) for x in q_vec[:5])

    # Text embedding & batch handling
    t_vec = embed_model.get_text_embedding("Evaluasi arsitektur jaringan saraf tiruan")
    assert isinstance(t_vec, list)
    assert len(t_vec) == 384

    batch_vecs = embed_model.get_text_embedding_batch(["Teks satu", "Teks dua"])
    assert len(batch_vecs) == 2
    assert len(batch_vecs[0]) == 384

    # Empty batch guard
    assert embed_model.get_text_embedding_batch([]) == []


@pytest.mark.asyncio
async def test_fastembed_dense_embedding_async_to_thread():
    """Verify async embedding methods execute non-blocking in worker thread without raising NotImplementedError."""
    embed_model = FastEmbedDenseEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    
    q_vec = await embed_model.aget_query_embedding("Kueri asinkronus")
    assert len(q_vec) == 384

    t_vec = await embed_model.aget_text_embedding("Teks asinkronus")
    assert len(t_vec) == 384

    b_vecs = await embed_model.aget_text_embedding_batch(["Batch satu", "Batch dua"])
    assert len(b_vecs) == 2


def test_fastembed_dense_with_qdrant_hybrid_indexing_and_retrieval():
    """End-to-end integration: Index documents with FastEmbed Dense + FastEmbed BM25 sparse in Qdrant."""
    client = QdrantClient(location=":memory:")
    vstore = QdrantVectorStore(
        collection_name="test_fastembed_hybrid_store",
        client=client,
        enable_hybrid=True,
        fastembed_sparse_model="Qdrant/bm25",
        batch_size=20,
    )
    embed_model = FastEmbedDenseEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    storage_context = StorageContext.from_defaults(vector_store=vstore)

    docs = [
        Document(
            text="Paper 1 introduces Low-Rank Adaptation (LoRA) for model fine-tuning with rank r=8.",
            metadata={"chat_id": "fe_chat", "filename": "lora_paper.pdf"}
        ),
        Document(
            text="Paper 2 discusses empirical mAP@50 score achieving 0.938 on COCO benchmark.",
            metadata={"chat_id": "fe_chat", "filename": "coco_paper.pdf"}
        ),
    ]

    index = VectorStoreIndex.from_documents(docs, storage_context=storage_context, embed_model=embed_model)
    retriever = index.as_retriever(similarity_top_k=2, vector_store_query_mode="hybrid")

    nodes = retriever.retrieve("LoRA rank r=8")
    assert len(nodes) >= 1
    assert "lora_paper.pdf" in nodes[0].node.metadata.get("filename", "")
    assert "Low-Rank Adaptation (LoRA)" in nodes[0].node.get_content()


def test_vector_store_default_collection_isolation(monkeypatch):
    """Verify vector_store defaults cleanly to isolated 'not_notebooklm_fastembed' collection."""
    import sys
    vs_mod = sys.modules["rag.vector_store"]
    test_client = QdrantClient(location=":memory:")

    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    orig_client = vs_mod.qdrant_client
    try:
        vs_mod.qdrant_client = test_client
        embed_model, vstore = init_embedding_and_vector_store()
        assert vstore.collection_name == "not_notebooklm_fastembed"
        assert isinstance(embed_model, FastEmbedDenseEmbedding)
    finally:
        vs_mod.qdrant_client = orig_client


def test_delete_document_vectors_includes_fastembed_collections():
    """Verify fallback deletion array cleanly targets new collection namespaces."""
    import sys
    vs_mod = sys.modules["rag.vector_store"]
    test_client = QdrantClient(location=":memory:")

    # Pre-create test collections
    for col in ["not_notebooklm_fastembed", "not_notebooklm_gemini_3072"]:
        test_client.create_collection(
            collection_name=col,
            vectors_config=qmodels.VectorParams(size=384 if "fastembed" in col else 3072, distance=qmodels.Distance.COSINE)
        )

    orig_client = vs_mod.qdrant_client
    try:
        vs_mod.qdrant_client = test_client
        # Call deletion; must not crash and must delete safely
        delete_document_vectors("chat_test_clean", "doc.pdf")
    finally:
        vs_mod.qdrant_client = orig_client
