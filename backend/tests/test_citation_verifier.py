import pytest
from evaluation.metrics.citation_verifier import verify_citation_fidelity, is_quote_in_document


def test_quote_in_document_exact_and_fuzzy():
    doc = "Convolutional neural networks have achieved state-of-the-art results in computer vision tasks."
    
    # Exact substring
    assert is_quote_in_document("Convolutional neural networks have achieved state-of-the-art", doc)
    
    # Minor whitespace differences
    assert is_quote_in_document("Convolutional   neural  networks \n have achieved", doc)
    
    # Non-existent quote
    assert not is_quote_in_document("Recurrent neural networks with LSTM and GRU memory units", doc)


def test_verify_citation_fidelity_perfect():
    doc1 = "The Transformer model uses multi-head self-attention mechanisms without any recurrence."
    doc2 = "BERT was trained on BooksCorpus and English Wikipedia with masked language modeling."
    
    response = """
    Arsitektur Transformer tidak mengandalkan rekurensi [1]. 
    Model BERT dilatih pada BooksCorpus [2].
    <!-- CITATION_MAP: {
        "1": ["The Transformer model uses multi-head self-attention mechanisms without any recurrence."],
        "2": ["BERT was trained on BooksCorpus and English Wikipedia"]
    } -->
    """
    
    report = verify_citation_fidelity(response, {"1": doc1, "2": doc2})
    assert report.ieee_syntax_score == 1.0
    assert report.citation_map_present is True
    assert report.total_tags_found == 2
    assert report.total_quotes_checked == 2
    assert report.quotes_verified == 2
    assert report.verbatim_fidelity_score == 1.0
    assert len(report.syntax_violations) == 0
    assert len(report.unmatched_quotes) == 0


def test_verify_citation_fidelity_syntax_violation():
    doc1 = "ResNet introduces residual connections to solve vanishing gradients."
    
    # Bad syntax: citation placed AFTER period
    response = """
    ResNet menggunakan residual connections. [1]
    <!-- CITATION_MAP: {
        "1": ["ResNet introduces residual connections to solve vanishing gradients."]
    } -->
    """
    
    report = verify_citation_fidelity(response, {"1": doc1})
    assert report.ieee_syntax_score < 1.0
    assert len(report.syntax_violations) > 0
    assert report.verbatim_fidelity_score == 1.0


def test_verify_citation_fidelity_unmatched_quote():
    doc1 = "YOLOv4 is an efficient and powerful object detection model."
    
    # Fake quote not in document
    response = """
    YOLOv4 mencapai 99.9% mAP pada dataset custom [1].
    <!-- CITATION_MAP: {
        "1": ["YOLOv4 achieves 99.9% mAP on custom dataset with zero false positives."]
    } -->
    """
    
    report = verify_citation_fidelity(response, {"1": doc1})
    assert report.ieee_syntax_score == 1.0
    assert report.total_quotes_checked == 1
    assert report.quotes_verified == 0
    assert report.verbatim_fidelity_score == 0.0
    assert len(report.unmatched_quotes) == 1
