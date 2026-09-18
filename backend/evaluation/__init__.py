"""
Evaluation package for Not-NotebookLM.
Provides unified benchmarks, multi-framework evaluators (Ragas, DeepEval, LlamaIndex, TruLens, Promptfoo),
and scientific datasets (QASPER, ALCE, SciFact, AttributedQA, CRAG).
"""

import sys
import types

# Ensure compatibility shims for deprecated modules in langchain_community
if 'langchain_community.chat_models.vertexai' not in sys.modules:
    dummy_vertex = types.ModuleType('langchain_community.chat_models.vertexai')
    dummy_vertex.ChatVertexAI = type('ChatVertexAI', (), {})
    sys.modules['langchain_community.chat_models.vertexai'] = dummy_vertex

if 'langchain_community.llms' not in sys.modules:
    dummy_llms = types.ModuleType('langchain_community.llms')
    dummy_llms.VertexAI = type('VertexAI', (), {})
    sys.modules['langchain_community.llms'] = dummy_llms
