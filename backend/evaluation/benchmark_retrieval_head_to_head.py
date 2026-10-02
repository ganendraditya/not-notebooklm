import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from llama_index.core import Document, VectorStoreIndex, StorageContext
from llama_index.core.embeddings import BaseEmbedding
from fastembed import TextEmbedding

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from rag.vector_store import QdrantVectorStore
from rag.academic_chunker import split_markdown_into_academic_sections

print("=" * 80)
print("COMPREHENSIVE RETRIEVAL BENCHMARK: DENSE-ONLY vs BM25 HYBRID (ISSUE #9)")
print("=" * 80)

# 1. Initialize Multilingual Dense Embedding Model (Shared across both systems)
print("\n[1/4] Loading Multilingual Dense Embedding Model (paraphrase-multilingual-MiniLM-L12-v2)...")
dense_engine = TextEmbedding("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

class FastEmbedDenseEmbedding(BaseEmbedding):
    def _get_query_embedding(self, query: str) -> List[float]:
        return list(dense_engine.embed([query]))[0].tolist()

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_query_embedding(query)

    def _get_text_embedding(self, text: str) -> List[float]:
        return list(dense_engine.embed([text]))[0].tolist()

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return [vec.tolist() for vec in dense_engine.embed(texts)]

embed_model = FastEmbedDenseEmbedding()
print("Multilingual dense model loaded successfully (384 dimensions).")

# 2. Load and Chunk All Real Papers from val25_benchmark.json
print("\n[2/4] Loading and chunking 16 authentic papers via Academic Chunker...")
val25_path = BACKEND_DIR / "evaluation" / "datasets" / "val25_benchmark.json"
papers_dir = BACKEND_DIR / "evaluation" / "datasets" / "qasper_papers"

with open(val25_path, "r", encoding="utf-8") as f:
    all_cases = json.load(f)

# Filter for answerable cases
test_cases = [c for c in all_cases if not c.get("unanswerable")]
print(f"Loaded {len(test_cases)} answerable benchmark cases from val25_benchmark.json")

# Collect unique papers
unique_papers = sorted(list(set(doc for c in test_cases for doc in c.get("target_documents", []))))
print(f"Total unique research papers involved: {len(unique_papers)}")

corpus_documents = []
for p in unique_papers:
    p_path = papers_dir / p
    if not p_path.exists():
        print(f"Warning: {p} not found!")
        continue
    with open(p_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    chunks = split_markdown_into_academic_sections(content, filename=p)
    for idx, c in enumerate(chunks):
        corpus_documents.append(Document(
            text=c.get("text", ""),
            metadata={
                "filename": p,
                "section": c.get("section", ""),
                "breadcrumb": c.get("breadcrumb", ""),
                "chunk_id": f"{p}_{idx}",
            }
        ))

print(f"Total production chunks indexed into corpus: {len(corpus_documents)}")

# 3. Setup Qdrant Vector Stores
print("\n[3/4] Indexing corpus into Qdrant stores (Dense-Only vs BM25 Hybrid)...")

# System 1: Dense-Only (BEFORE)
client_dense = QdrantClient(location=":memory:")
vstore_dense = QdrantVectorStore(
    collection_name="eval_dense_only",
    client=client_dense,
    enable_hybrid=False,
    batch_size=20,
)
storage_dense = StorageContext.from_defaults(vector_store=vstore_dense)
index_dense = VectorStoreIndex.from_documents(corpus_documents, storage_context=storage_dense, embed_model=embed_model)
retriever_dense = index_dense.as_retriever(similarity_top_k=10, vector_store_query_mode="default")

# System 2: BM25 Hybrid (AFTER)
client_hybrid = QdrantClient(location=":memory:")
vstore_hybrid = QdrantVectorStore(
    collection_name="eval_hybrid_bm25",
    client=client_hybrid,
    enable_hybrid=True,
    fastembed_sparse_model="Qdrant/bm25",
    batch_size=20,
)
storage_hybrid = StorageContext.from_defaults(vector_store=vstore_hybrid)
index_hybrid = VectorStoreIndex.from_documents(corpus_documents, storage_context=storage_hybrid, embed_model=embed_model)
retriever_hybrid = index_hybrid.as_retriever(similarity_top_k=10, vector_store_query_mode="hybrid")
print("Both indices built successfully.")

# 4. Evaluation Execution & Metrics Calculation
print("\n[4/4] Executing head-to-head retrieval evaluation across all 21 cases...")

def is_node_a_hit(node_content: str, node_filename: str, case: Dict[str, Any]) -> bool:
    target_docs = case.get("target_documents", [])
    if node_filename not in target_docs:
        return False
    
    # For single_fact and scifact, check evidence spans or ground truth keywords
    spans = case.get("evidence_spans", [])
    if spans:
        for span in spans:
            clean_span = span.strip().lower()
            if len(clean_span) > 80:
                # Substring matching with first 50 chars for long sentences
                sub = clean_span[:50]
                if sub in node_content.lower():
                    return True
            else:
                if clean_span in node_content.lower():
                    return True
        # If explicit spans exist but none matched, do not fall through
        return False
    
    # Fallback to ground truth if evidence spans is empty
    gt = str(case.get("ground_truth", "")).strip().lower()
    if gt and len(gt) > 3 and gt in node_content.lower():
        return True
    
    # For multi-paper queries without explicit spans, any chunk from target docs counts toward doc coverage
    if case.get("category") == "multi_comparative":
        return True
    
    return False

results = []
dense_ranks = []
hybrid_ranks = []

for c in test_cases:
    query = c.get("query")
    cid = c.get("id")
    category = c.get("category")
    target_docs = c.get("target_documents", [])

    # Retrieve Top-10
    nodes_dense = retriever_dense.retrieve(query)
    nodes_hybrid = retriever_hybrid.retrieve(query)

    # Find first Hit Rank in Dense
    d_hit_rank = None
    for r_idx, n in enumerate(nodes_dense):
        if is_node_a_hit(n.node.get_content(), n.node.metadata.get("filename", ""), c):
            d_hit_rank = r_idx + 1
            break

    # Find first Hit Rank in Hybrid
    h_hit_rank = None
    for r_idx, n in enumerate(nodes_hybrid):
        if is_node_a_hit(n.node.get_content(), n.node.metadata.get("filename", ""), c):
            h_hit_rank = r_idx + 1
            break

    # Multi-paper document coverage
    d_covered_docs = len(set(n.node.metadata.get("filename") for n in nodes_dense if n.node.metadata.get("filename") in target_docs))
    h_covered_docs = len(set(n.node.metadata.get("filename") for n in nodes_hybrid if n.node.metadata.get("filename") in target_docs))
    total_target_docs = len(target_docs)

    dense_ranks.append(d_hit_rank)
    hybrid_ranks.append(h_hit_rank)

    # Determine individual outcome
    if d_hit_rank is None and h_hit_rank is not None:
        outcome = "RECOVERED (+)"
    elif d_hit_rank is not None and h_hit_rank is None:
        outcome = "LOST (-)"
    elif d_hit_rank is not None and h_hit_rank is not None:
        if h_hit_rank < d_hit_rank:
            outcome = f"PROMOTED (+{d_hit_rank - h_hit_rank})"
        elif h_hit_rank > d_hit_rank:
            outcome = f"REGRESSED (-{h_hit_rank - d_hit_rank})"
        else:
            outcome = "TIED (=)"
    else:
        outcome = "MISSED (x)"

    results.append({
        "id": cid,
        "category": category,
        "query": query,
        "dense_rank": d_hit_rank,
        "hybrid_rank": h_hit_rank,
        "outcome": outcome,
        "d_cov": f"{d_covered_docs}/{total_target_docs}",
        "h_cov": f"{h_covered_docs}/{total_target_docs}",
    })

# Compute Aggregate Metrics
def compute_mrr(ranks: List[Optional[int]]) -> float:
    if not ranks:
        return 0.0
    return sum((1.0 / r) if r is not None and r <= 10 else 0.0 for r in ranks) / len(ranks)

def compute_recall_at_k(ranks: List[Optional[int]], k: int) -> float:
    if not ranks:
        return 0.0
    return sum(1 for r in ranks if r is not None and r <= k) / len(ranks)

mrr_dense = compute_mrr(dense_ranks)
mrr_hybrid = compute_mrr(hybrid_ranks)

recall10_dense = compute_recall_at_k(dense_ranks, 10)
recall10_hybrid = compute_recall_at_k(hybrid_ranks, 10)

recall5_dense = compute_recall_at_k(dense_ranks, 5)
recall5_hybrid = compute_recall_at_k(hybrid_ranks, 5)

recall1_dense = compute_recall_at_k(dense_ranks, 1)
recall1_hybrid = compute_recall_at_k(hybrid_ranks, 1)

promoted_count = sum(1 for r in results if "PROMOTED" in r["outcome"] or "RECOVERED" in r["outcome"])
regressed_count = sum(1 for r in results if "REGRESSED" in r["outcome"] or "LOST" in r["outcome"])
tied_count = sum(1 for r in results if "TIED" in r["outcome"])
missed_count = sum(1 for r in results if "MISSED" in r["outcome"])

# Print Detailed Case-by-Case Breakdown
print("\n" + "=" * 105)
print(f"{'Case ID':<15} | {'Category':<14} | {'Dense (Before)':<15} | {'Hybrid (After)':<15} | {'Doc Cov (D/H)':<14} | {'Outcome':<16}")
print("=" * 105)
for r in results:
    d_str = f"Rank #{r['dense_rank']}" if r['dense_rank'] else "Missed (>10)"
    h_str = f"Rank #{r['hybrid_rank']}" if r['hybrid_rank'] else "Missed (>10)"
    cov_str = f"{r['d_cov']} vs {r['h_cov']}"
    print(f"{r['id']:<15} | {r['category'][:13]:<14} | {d_str:<15} | {h_str:<15} | {cov_str:<14} | {r['outcome']:<16}")
print("=" * 105)

# Print Final Scientific Scorecard
print("\n" + "=" * 60)
print("           OFFICIAL BENCHMARK SCORECARD (N=21)")
print("=" * 60)
print(f"{'Metric':<25} | {'Dense-Only':<12} | {'BM25 Hybrid':<12} | {'Delta':<10}")
print("-" * 60)
print(f"{'MRR@10 (Primary)':<25} | {mrr_dense:.4f}{'':<6} | {mrr_hybrid:.4f}{'':<6} | {mrr_hybrid - mrr_dense:+.4f}")
print(f"{'Recall@10':<25} | {recall10_dense*100:.1f}%{'':<7} | {recall10_hybrid*100:.1f}%{'':<7} | {(recall10_hybrid - recall10_dense)*100:+.1f}%")
print(f"{'Recall@5':<25} | {recall5_dense*100:.1f}%{'':<7} | {recall5_hybrid*100:.1f}%{'':<7} | {(recall5_hybrid - recall5_dense)*100:+.1f}%")
print(f"{'Top-1 Precision':<25} | {recall1_dense*100:.1f}%{'':<7} | {recall1_hybrid*100:.1f}%{'':<7} | {(recall1_hybrid - recall1_dense)*100:+.1f}%")
print("-" * 60)
print(f"Head-to-Head Headcount:")
total_cases = len(results) or 1
print(f"  • Improved / Promoted / Recovered : {promoted_count} cases ({(promoted_count/total_cases)*100:.1f}%)")
print(f"  • Tied (Same rank)                : {tied_count} cases ({(tied_count/total_cases)*100:.1f}%)")
print(f"  • Regressed / Lower               : {regressed_count} cases ({(regressed_count/total_cases)*100:.1f}%)")
print(f"  • Both Missed                     : {missed_count} cases ({(missed_count/total_cases)*100:.1f}%)")
print("=" * 60)
