"""
Live Test: Verifying AI Self-Correction via Document Context
Proves that when user corrects the AI pointing to a real section,
the AI does NOT stubbornly hold its previous claim, but re-verifies
the context and updates its stance.
"""

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from llama_index.core.llms import ChatMessage, MessageRole
from rag.llm_factory import get_main_llm
from rag.prompts import get_workspace_analysis_system_prompt

pytestmark = pytest.mark.live


@pytest.mark.asyncio
async def test_re_verification_and_self_correction_when_user_corrects():
    llm = get_main_llm()
    system_prompt = get_workspace_analysis_system_prompt(doc_count=1)

    # Dokumen dengan detail tersembunyi di bagian akhir
    doc_context = (
        "[Document 1]: Deep Learning Model Benchmark (2024).\n"
        "Abstract: Evaluated Vision Transformer on ImageNet.\n"
        "Introduction: ViT shows strong performance.\n"
        "Appendix C (Ablation Studies): When training with stochastic depth drop rate of 0.2, "
        "the model achieves an exact accuracy of 83.7%."
    )

    # --- Turn 1: Pertanyaan umum di mana AI mungkin melewatkan Appendix ---
    user_q1 = "Apakah model ini ada pengujian dengan stochastic depth drop rate?"
    
    # Simulated Turn 1 where model initially missed the appendix
    simulated_initial_wrong_answer = (
        "This detail is not found in the documents currently available in the system. "
        "The document only discusses general Vision Transformer evaluation on ImageNet [1]."
    )

    # --- Turn 2: User membetulkan dengan petunjuk nyata dari dokumen ---
    user_correction = (
        "Coba cek lagi yang bener, jangan buru-buru bilang ga ada! "
        "Di Appendix C (Ablation Studies) ada kok pengujian stochastic depth drop rate 0.2. "
        "Berapa akurasinya di situ?"
    )

    messages = [
        ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
        ChatMessage(role=MessageRole.USER, content=f"Reference Documents:\n{doc_context}\n\nQuestion: {user_q1}"),
        ChatMessage(role=MessageRole.ASSISTANT, content=simulated_initial_wrong_answer),
        ChatMessage(role=MessageRole.USER, content=user_correction),
    ]

    print("\n--- SENDING USER CORRECTION TO MODEL ---")
    resp = await llm.achat(messages)
    text = resp.message.content.strip()

    print("\n--- MODEL RESPONSE AFTER CORRECTION ---")
    print(text)

    # --- VERIFIKASI LOGIKA ---
    # 1. AI TIDAK BOLEH NGEYEL BATU (e.g. "Tetap tidak ada!")
    assert not any(batu in text.lower() for batu in [
        "tetap tidak ditemukan", "sudah saya katakan tidak ada", "dokumen tidak memiliki appendix"
    ]), "Model ngeyel batu dan menolak mengecek dokumen!"

    # 2. AI HARUS MENGAKUI FAKTA DARI DOKUMEN (83.7%)
    assert "83.7" in text or "83,7" in text, "Model gagal memverifikasi angka akurasi 83.7% dari teks!"

    # 3. AI HARUS MEMASANG CITATION DENGAN BENAR
    assert "[1]" in text, "Model tidak memasang sitasi pada fakta yang dikoreksi"
