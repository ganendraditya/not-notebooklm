"""
Curator for High-Entropy Protocol B Benchmark Matrices:
- niah_100_matrix.json (100-Case Test Suite across 4 balanced quadrants @ 25 cases)
- niah_val25_matrix.json (25-Case Val Suite across 4 balanced quadrants: 7 S, 6 M, 6 R, 6 U)

Features:
1. High Entropy & Linguistic Diversity across 6 Human Personas:
   - casual_slang (Indonesian/English colloquial)
   - academic_verbose (Formal professor / ethics committee)
   - terse_lowercase (Minimalist, lowercase, no punctuation)
   - broken_english (Non-native speaker)
   - all_caps_urgent (High urgency / ALL-CAPS)
   - confused_beginner (Student / self-taught)
2. Dynamic Probe Positioning (probe_ratio from 0.35 to 1.0)
3. Negative / Unanswerable Traps (U-NIAH) testing abstention honesty
4. Temporal Rule Updates (superseding directives)
5. Zero Overlap / Anti-Leakage between Val-25 and Test-100
"""

import json
from pathlib import Path
from typing import List, Dict, Any

DATASETS_DIR = Path(__file__).resolve().parent
PAPERS_DIR = DATASETS_DIR / "qasper_papers"
TEST_100_PATH = DATASETS_DIR / "niah_100_matrix.json"
VAL_25_PATH = DATASETS_DIR / "niah_val25_matrix.json"

# Collect available papers for haystacks
test_papers = [
    "qasper_1604.02038.txt", "qasper_1609.00425.txt", "qasper_1611.06322.txt",
    "qasper_1704.06194.txt", "qasper_1705.09665.txt", "qasper_1801.05147.txt",
    "qasper_1805.02400.txt", "qasper_1810.02229.txt", "qasper_1810.08699.txt",
    "qasper_1811.00383.txt", "qasper_1811.00942.txt", "qasper_1904.09131.txt",
    "qasper_1905.00840.txt", "qasper_1907.05664.txt", "qasper_1908.06606.txt",
    "qasper_1909.00091.txt", "qasper_1909.00512.txt", "qasper_1909.00694.txt",
    "qasper_1909.09067.txt", "qasper_1910.14497.txt", "qasper_1911.04474.txt",
    "qasper_1911.10742.txt", "qasper_1912.01214.txt", "qasper_2003.03106.txt",
    "qasper_2003.07723.txt"
]

val_papers = [
    "qasper_1809.00540.txt", "qasper_2004.03354.txt", "qasper_1611.04798.txt",
    "qasper_1912.13337.txt", "qasper_1809.01541.txt", "qasper_1809.09194.txt",
    "qasper_1604.05372.txt", "qasper_2002.08795.txt"
]


def generate_test_100_cases() -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []

    # --------------------------------------------------------------------------
    # QUADRANT 1: 25 S-NIAH Cases (5x5 Grid: 4K, 8K, 16K, 32K, 64K x 10%, 30%, 50%, 70%, 90%)
    # --------------------------------------------------------------------------
    loads = ["4k", "8k", "16k", "32k", "64k"]
    depths = [0.10, 0.30, 0.50, 0.70, 0.90]

    s_specs = [
        # 4k
        ("casual_slang", "eh bro pembimbing gw wantinya pake korpus multiun aja ya, jgn coba2 pake europarl", "MultiUN corpus only (never Europarl).", "Apa korpus yang diwajibkan pembimbing saya tadi?"),
        ("terse_lowercase", "batch: 64, seed: 9901, no gpl libraries allowed", "Batch size 64, random seed 9901, strictly no GPL libraries.", "what batch size and random seed did i specify?"),
        ("broken_english", "please note our server is only 16gb ram zero swap, cannot load big model", "Server has only 16GB RAM with zero swap space.", "How much RAM does our server possess according to earlier note?"),
        ("academic_verbose", "Pursuant to Institutional Ethics Protocol #2026-B81, human subjects must be explicitly de-identified.", "Institutional Ethics Protocol #2026-B81 requires explicit de-identification.", "What was the ethics protocol number I stated earlier?"),
        ("all_caps_urgent", "NOTICE: MUST RESAMPLE ALL SPEECH WAVEFORMS TO EXACTLY 16000HZ!", "Speech waveforms must be resampled to 16000Hz (16kHz).", "What audio sampling rate did I mandate in my urgent notice?"),

        # 8k
        ("confused_beginner", "laptop saya cuma punya GPU RTX 3060 6GB VRAM, jangan rekomendasi model yg butuh VRAM lebih dari itu ya min", "Maximum 6GB VRAM (NVIDIA RTX 3060 constraint).", "Berapa batas maksimum VRAM GPU yang saya miliki?"),
        ("casual_slang", "inget ya boss kita cuma targetin deployment di apple silicon mps, jangan pake cuda", "Target deployment is Apple Silicon Metal (MPS backend); no CUDA.", "Target hardware apa yang saya sebutkan untuk deployment?"),
        ("terse_lowercase", "quantization: 4-bit awq group size 128 only", "4-bit AWQ with group size 128.", "what quantization format and group size did i set?"),
        ("academic_verbose", "The clinical diagnostic cohort was contributed exclusively by Charité University Hospital Berlin.", "Contributed exclusively by Charité University Hospital Berlin.", "Which medical institution contributed the diagnostic cohort?"),
        ("broken_english", "we must fix adamw weight decay to 0.015 with cosine annealing schedule", "AdamW weight decay fixed at 0.015 with cosine annealing.", "What weight decay value and annealing schedule did I specify?"),

        # 16k
        ("all_caps_urgent", "SECURITY DIRECTIVE: NEVER STORE UNENCRYPTED ACCESS TOKENS IN THE REDIS CACHE!", "Never store unencrypted access tokens in Redis cache.", "What was my urgent security rule regarding the Redis cache?"),
        ("confused_beginner", "saya dapet pesan error katanya learning rate harus diset 3e-4, tolong inget ya peak lr kita 3e-4", "Peak learning rate must be set to 3e-4.", "Berapa nilai peak learning rate yang saya minta catat tadi?"),
        ("casual_slang", "catat ya, kita cuma submit paper ini khusus buat venue ACL 2026, bukan EMNLP", "Submission is exclusively targeted for ACL 2026 (not EMNLP).", "Target venue konferensi apa yang saya sebutkan tadi?"),
        ("terse_lowercase", "metric: report only expected calibration error 15 bins ece-15", "Report only Expected Calibration Error with 15 bins (ECE-15).", "which calibration metric did i ask to report?"),
        ("academic_verbose", "Cohort eligibility criteria strictly mandate a minimum participant age threshold of 45 years.", "Minimum participant age threshold of 45 years.", "What was the minimum cohort age threshold established earlier?"),

        # 32k
        ("broken_english", "our mobile app only support on-device inference with coreml format", "Mobile app strictly supports on-device inference using CoreML format.", "Which mobile inference framework did I state our app supports?"),
        ("all_caps_urgent", "STOP: MAXIMUM CONTEXT WINDOW FOR LOCAL RERANKER IS CAPPED AT 2048 TOKENS!", "Local reranker maximum context length is hard-capped at 2048 tokens.", "What is the maximum token cap for our local reranker?"),
        ("confused_beginner", "kata dosen saya loss function harus pake Dice Loss bukan Cross Entropy biasa", "Loss function must use Dice Loss instead of Cross Entropy.", "Apa fungsi loss yang disuruh dosen saya gunakan tadi?"),
        ("casual_slang", "eh iya, token pooling-nya wajib mean-pooling ya, jangan sekali-kali pake CLS token", "Must use mean-token pooling; strictly never use CLS token pooling.", "Metode token pooling apa yang saya wajibkan tadi?"),
        ("terse_lowercase", "vector cache ttl: fixed at 86400 seconds 24 hours in redis port 6389", "Vector cache key TTL fixed at 86400 seconds on Redis port 6389.", "what is the vector cache ttl in seconds?"),

        # 64k
        ("academic_verbose", "It is an unalterable operational requirement that the text embedding backbone remain RoBERTa-large with 355M parameters.", "Text embedding backbone must be RoBERTa-large (355M parameters).", "What exact text embedding backbone architecture was mandated?"),
        ("broken_english", "we cannot use spacy or stanford ner library, we write crf from scratch", "Cannot use spaCy or Stanford NER; must implement custom CRF.", "Which two NER libraries did I forbid earlier?"),
        ("all_caps_urgent", "CRITICAL THRESHOLD: MINIMUM TEST ACCURACY BEFORE MERGING IS 92.5 PERCENT!", "Minimum test accuracy threshold before merging is 92.5%.", "What was the critical test accuracy percentage threshold I set?"),
        ("confused_beginner", "saya simpan file modelnya di folder /opt/checkpoints/best_model.pt, jangan lupa path-nya ya min", "Model checkpoint path is /opt/checkpoints/best_model.pt.", "Di folder path mana saya menyimpan file model tadi?"),
        ("casual_slang", "inget ya kita rilis pake lisensi apache 2.0, haram hukumnya masukin kode agpl", "Repository released under Apache 2.0; AGPL code strictly prohibited.", "Apa lisensi open source kita dan lisensi apa yang dilarang keras?")
    ]

    idx = 0
    for l_idx, load in enumerate(loads):
        for d_idx, depth in enumerate(depths):
            persona, needle_text, expected, probe = s_specs[idx]
            cases.append({
                "id": f"S-NIAH-{idx+1:02d}",
                "tier": "s_niah",
                "token_load": load,
                "depth_ratio": depth,
                "persona": persona,
                "probe_ratio": 1.0,
                "target_documents": [test_papers[idx % len(test_papers)]],
                "needles": [
                    {
                        "input": needle_text,
                        "depth_ratio": depth,
                        "type": "directive",
                        "persona": persona
                    }
                ],
                "expected_answer": expected,
                "probe_query": probe
            })
            idx += 1

    # --------------------------------------------------------------------------
    # QUADRANT 2: 25 M-NIAH Cases (Multi-Needle with Dynamic Probe Depths)
    # --------------------------------------------------------------------------
    m_specs = [
        # (persona, [(depth, needle)], probe_ratio, expected, probe)
        (
            "casual_slang",
            [(0.15, "eh bro ram server kita cuma 16gb ya"), (0.35, "trs gpu kita pake rtx 4090 vram 24gb")],
            0.50, # Dynamic mid-conversation probe!
            "RAM server 16GB dan GPU RTX 4090 dengan 24GB VRAM.",
            "tadi gw sempet sebut spek RAM sama GPU server kita berapa ya?"
        ),
        (
            "terse_lowercase",
            [(0.10, "audio rate: 16000hz"), (0.75, "mel channels: 80")],
            1.0,
            "Sampling rate is 16000Hz and mel channels is 80.",
            "what are the audio rate and mel channels i set earlier?"
        ),
        (
            "academic_verbose",
            [(0.20, "Protocol requires minimum subject age of 45 years."), (0.80, "Exclude any patient receiving corticosteroid therapy.")],
            1.0,
            "Minimum age 45 years and exclusion of patients receiving corticosteroid therapy.",
            "What were the minimum subject age and medication exclusion criteria specified?"
        ),
        (
            "broken_english",
            [(0.10, "save checkpoint every 2000 step"), (0.30, "warmup step is 500"), (0.65, "max learning rate is 3e-4")],
            0.75, # Interleaved mid-probe
            "Checkpoint interval 2000 steps, warmup 500 steps, peak learning rate 3e-4.",
            "what three training values i gave: checkpoint interval, warmup step, and max lr?"
        ),
        (
            "all_caps_urgent",
            [(0.15, "RULE 1: RESERVE EXACTLY 15 PERCENT DATA FOR OOD EVALUATION!"), (0.70, "RULE 2: SEED MUST BE FIXED AT 777!")],
            1.0,
            "15% data for OOD evaluation and random seed 777.",
            "WHAT WERE THE TWO DATA SPLIT RULES REGARDING OOD PERCENTAGE AND SEED?"
        ),
        (
            "confused_beginner",
            [(0.25, "saya cuma boleh pake dataset publik kata dosen"), (0.75, "terus minimal data test harus 500 baris katanya")],
            1.0,
            "Hanya dataset publik dan minimal 500 baris data test.",
            "dua aturan dataset apa yang disuruh dosen saya tadi?"
        ),
        (
            "casual_slang",
            [(0.10, "jgn pake spacy ya"), (0.45, "jgn pake stanford ner juga"), (0.85, "pake custom crf aja")],
            1.0,
            "Dilarang pakai spaCy dan Stanford NER; harus pakai custom CRF.",
            "library apa aja yg dilarang dan model apa yg disuruh pake?"
        ),
        (
            "terse_lowercase",
            [(0.20, "embedding dim: 512"), (0.40, "hidden layers: 12")],
            0.60, # Mid probe
            "Embedding dimension is 512 and hidden layers is 12.",
            "what embedding dim and layer count did i specify earlier?"
        ),
        (
            "academic_verbose",
            [(0.15, "The primary clinical endpoint is 30-day progression-free survival."), (0.75, "Statistical significance threshold is pre-specified at alpha=0.01.")],
            1.0,
            "Primary endpoint is 30-day progression-free survival with significance threshold alpha=0.01.",
            "What primary clinical endpoint and alpha threshold were established earlier?"
        ),
        (
            "broken_english",
            [(0.10, "we use bpe tokenizer vocab 32000"), (0.80, "dropout rate is 0.1")],
            1.0,
            "BPE tokenizer with vocabulary size 32000 and dropout rate 0.1.",
            "what tokenizer vocab size and dropout rate did i tell you?"
        ),
        (
            "all_caps_urgent",
            [(0.20, "MANDATE: USE ADAMW WITH WEIGHT DECAY 0.01!"), (0.80, "MANDATE: COSINE LR SCHEDULER ONLY!")],
            1.0,
            "AdamW optimizer with weight decay 0.01 and cosine scheduler.",
            "WHAT OPTIMIZER AND SCHEDULER COMBINATION DID I INSTRUCT EARLIER?"
        ),
        (
            "confused_beginner",
            [(0.15, "min saya lupa tadi nyebut port redis 6389"), (0.40, "sama passwordnya secrettoken123")],
            0.55, # Mid probe
            "Port Redis 6389 dan password secrettoken123.",
            "berapa port redis dan password yang tadi saya sebutin?"
        ),
        (
            "casual_slang",
            [(0.20, "gpu cluster kita ada 8 node"), (0.80, "masing2 node punya 4 a100")],
            1.0,
            "8 cluster nodes with 4 NVIDIA A100 GPUs per node (32 A100s total).",
            "berapa jumlah node dan gpu per node di cluster kita tadi?"
        ),
        (
            "terse_lowercase",
            [(0.10, "max input tokens: 4096"), (0.70, "max output tokens: 512")],
            1.0,
            "Max input tokens is 4096 and max output tokens is 512.",
            "what are the max input and output token limits?"
        ),
        (
            "academic_verbose",
            [(0.25, "Institutional Review Board oversight is governed by Protocol #4402-A."), (0.85, "Cross-validation must strictly employ 10 stratified folds.")],
            1.0,
            "IRB Protocol #4402-A and 10 stratified cross-validation folds.",
            "What IRB protocol number and cross-validation fold count were specified?"
        ),
        (
            "broken_english",
            [(0.15, "our corpus has english and german language only"), (0.75, "no french data")],
            1.0,
            "Corpus contains English and German only (no French data).",
            "which two languages are in our corpus and which language is excluded?"
        ),
        (
            "all_caps_urgent",
            [(0.20, "ALERT: DEPLOYMENT DEVICE IS RASPBERRY PI 4!"), (0.80, "ALERT: OPERATING SYSTEM IS UBUNTU 22.04 LTS!")],
            1.0,
            "Raspberry Pi 4 running Ubuntu 22.04 LTS.",
            "WHAT HARDWARE DEVICE AND OS WAS MANDATED FOR DEPLOYMENT?"
        ),
        (
            "confused_beginner",
            [(0.10, "file datanya format parquet"), (0.45, "ukurannya kira2 250 megabyte")],
            0.60, # Mid probe
            "Format Parquet dengan ukuran sekitar 250MB.",
            "apa format file data dan ukurannya yang saya bilang tadi?"
        ),
        (
            "casual_slang",
            [(0.15, "loss-nya pake focal loss gamma 2.0 ya"), (0.80, "label smoothing diset 0.05 aja")],
            1.0,
            "Focal Loss dengan gamma 2.0 dan label smoothing 0.05.",
            "apa setting loss function dan label smoothing kita tadi?"
        ),
        (
            "terse_lowercase",
            [(0.20, "batch size: 32"), (0.50, "epochs: 50"), (0.85, "patience: 5")],
            1.0,
            "Batch size 32, epochs 50, early stopping patience 5.",
            "retrieve batch size, epochs, and early stopping patience."
        ),
        (
            "academic_verbose",
            [(0.10, "Experimental evaluation is strictly confined to the WMT16 English-Romanian benchmark."), (0.75, "Evaluation metric is detokenized SacreBLEU.")],
            1.0,
            "WMT16 English-Romanian benchmark evaluated using detokenized SacreBLEU.",
            "What benchmark dataset and evaluation BLEU variant were designated?"
        ),
        (
            "broken_english",
            [(0.20, "our model name is BiTrans-Tiny"), (0.80, "it has 15 million parameter")],
            1.0,
            "Model name is BiTrans-Tiny with 15 million parameters.",
            "what is the model name and parameter count?"
        ),
        (
            "all_caps_urgent",
            [(0.15, "RESTRICTION: MAX CONCURRENCY IS 4 WORKERS!"), (0.70, "TIMEOUT IS 120 SECONDS!")],
            1.0,
            "Max concurrency of 4 workers and 120-second timeout.",
            "WHAT ARE THE CONCURRENCY AND TIMEOUT SETTINGS?"
        ),
        (
            "confused_beginner",
            [(0.10, "min tolong catat seed 1337"), (0.40, "sama learning rate 1e-4 ya")],
            0.50, # Mid probe
            "Random seed 1337 dan learning rate 1e-4.",
            "berapa seed dan learning rate yang saya titip catat tadi?"
        ),
        (
            "casual_slang",
            [(0.20, "kita pake embedding bge-m3 ya bro"), (0.80, "reranker-nya pake bge-reranker-large")],
            1.0,
            "Embedding model bge-m3 dan reranker bge-reranker-large.",
            "model embedding sama reranker apa yg kita sepakati tadi?"
        )
    ]

    for m_idx, (persona, needles_data, p_ratio, expected, probe) in enumerate(m_specs):
        load = loads[m_idx % len(loads)]
        needles = [{"input": n_text, "depth_ratio": d_ratio, "type": "multi", "persona": persona} for d_ratio, n_text in needles_data]
        cases.append({
            "id": f"M-NIAH-{m_idx+1:02d}",
            "tier": "m_niah",
            "token_load": load,
            "depth_ratio": needles_data[-1][0],
            "probe_ratio": p_ratio,
            "persona": persona,
            "target_documents": [test_papers[(m_idx + 5) % len(test_papers)]],
            "needles": needles,
            "expected_answer": expected,
            "probe_query": probe
        })

    # --------------------------------------------------------------------------
    # QUADRANT 3: 25 R-NIAH Cases (Reasoning, Deductions & Temporal Updates)
    # --------------------------------------------------------------------------
    r_specs = [
        # (persona, [(depth, text)], p_ratio, expected, probe)
        (
            "casual_slang",
            [(0.15, "eh rtx 3090 kita vram-nya 24gb doang ya"), (0.70, "model 70b fp16 butuh vram 140gb buat loading")],
            1.0,
            "Tidak bisa, karena VRAM GPU cuma 24GB sedangkan model butuh 140GB (kurang 116GB, akan OOM).",
            "bisa gak gpu kita load model 70b fp16 secara native tanpa quantisasi?"
        ),
        (
            "terse_lowercase",
            [(0.15, "policy v1: batch size is 32"), (0.75, "superseding update policy v2: batch size is doubled to 64")],
            1.0,
            "Under policy v2, the current batch size is 64 (superseding 32).",
            "what is our current active batch size under policy v2?"
        ),
        (
            "academic_verbose",
            [(0.20, "Condition: If validation loss plateaus for 3 consecutive epochs, reduce learning rate by 50%."), (0.80, "Empirical observation: Validation loss remained 1.84 across epochs 12, 13, and 14 without improvement.")],
            1.0,
            "Yes, the learning rate must be reduced by 50% because validation loss plateaued for 3 consecutive epochs (epochs 12-14).",
            "Based on the plateau condition and empirical observations across epochs 12-14, should the learning rate be reduced?"
        ),
        (
            "broken_english",
            [(0.15, "rule: paper before year 2015 must be rejected"), (0.70, "candidate study published in year 2012")],
            1.0,
            "Rejected/excluded, because it was published in 2012 which is before 2015.",
            "can we accept the candidate study according to our publication year rule?"
        ),
        (
            "all_caps_urgent",
            [(0.15, "STAGE 2 INPUT REQUIRES NHWC TENSOR LAYOUT!"), (0.75, "STAGE 1 VISION BACKBONE STRICTLY OUTPUTS NCHW TENSOR LAYOUT!")],
            1.0,
            "No, a tensor transposition/permutation step (NCHW to NHWC) is required before Stage 2 can accept the output.",
            "CAN STAGE 2 DIRECTLY CONSUME STAGE 1 OUTPUT WITHOUT A TENSOR PERMUTATION?"
        ),
        (
            "confused_beginner",
            [(0.15, "tadi kata dosen minimal gain harus 2.5 BLEU dari baseline biar boleh dipake"), (0.75, "hasil test: baseline 31.2 BLEU, model kita 34.1 BLEU")],
            1.0,
            "Boleh/layak digunakan, karena gain-nya 2.9 BLEU (34.1 - 31.2), melebihi syarat minimal 2.5 BLEU.",
            "berdasarkan syarat minimal gain dan hasil test, apakah model kita layak digunakan?"
        ),
        (
            "casual_slang",
            [(0.15, "aturan awal: kita pake 4 node"), (0.40, "eh update bro, dapet hibah server jd node kita sekarang 10")],
            0.55, # Mid probe
            "10 node (aturan awal 4 node sudah diupdate setelah dapat hibah).",
            "total node cluster kita sekarang ada berapa ya?"
        ),
        (
            "terse_lowercase",
            [(0.20, "rule: if records < 500 use epsilon <= 1.0; if >= 500 use epsilon <= 2.5"), (0.75, "cohort audit: total verified records is 340")],
            1.0,
            "Epsilon must be <= 1.0 because 340 records is less than 500.",
            "what is the required differential privacy epsilon for our cohort?"
        ),
        (
            "academic_verbose",
            [(0.15, "Hypothesis A asserts that elevation of Aβ and tau phosphorylation occur through independent downstream cascades."), (0.80, "Laboratory observation confirms that inhibition of Aβ synthesis left tau hyperphosphorylation completely unaffected.")],
            1.0,
            "Yes, the laboratory observation supports Hypothesis A, demonstrating that tau phosphorylation operates independently of Aβ elevation.",
            "Does the laboratory observation substantiate or refute Hypothesis A regarding independent pathways?"
        ),
        (
            "broken_english",
            [(0.20, "gpu price is 2000 dollar each"), (0.75, "our total grant budget is 7000 dollar")],
            1.0,
            "Maximum 3 GPUs (3 x $2000 = $6000, 4 would be $8000 which exceeds budget).",
            "how many gpus can we buy within our total grant budget?"
        ),
        (
            "all_caps_urgent",
            [(0.15, "OLD SPEC: LEARNING RATE WAS 1E-3!"), (0.70, "REVISION: OVERFITTING DETECTED, REDUCE LEARNING RATE TO 2E-4!")],
            1.0,
            "Current learning rate is 2e-4 (revised from 1e-3).",
            "WHAT IS THE CURRENT LEARNING RATE FOLLOWING THE REVISION?"
        ),
        (
            "confused_beginner",
            [(0.15, "kuota token harian kita 100.000 token"), (0.75, "setiap request chat makan 5.000 token")],
            1.0,
            "Maksimal 20 request chat per hari (100.000 / 5.000 = 20).",
            "berapa maksimal request chat yang bisa kita lakukan dalam sehari?"
        ),
        (
            "casual_slang",
            [(0.15, "kalo akurasi < 90% kita ga boleh submit paper"), (0.45, "hasil akhir cuma tembus 87.5%")],
            0.60, # Mid probe
            "Tidak boleh submit, karena akurasi 87.5% masih di bawah syarat minimal 90%.",
            "apakah kita boleh submit paper dengan hasil akurasi kita saat ini?"
        ),
        (
            "terse_lowercase",
            [(0.15, "server a: 32gb ram"), (0.45, "server b: 64gb ram"), (0.80, "job needs 48gb ram")],
            1.0,
            "Server B can run the job (64GB >= 48GB), but Server A cannot (32GB < 48GB).",
            "which server can accommodate the job memory requirement?"
        ),
        (
            "academic_verbose",
            [(0.20, "Initial protocol mandated evaluation across all 15 low-resource language pairs."), (0.80, "Due to compute constraints, evaluation was formally pruned to only the top 5 highest-resource pairs.")],
            1.0,
            "Only 5 language pairs were evaluated (pruned from the initial 15 due to compute constraints).",
            "How many language pairs were ultimately evaluated according to the revised protocol?"
        ),
        (
            "broken_english",
            [(0.15, "we train model on 200 epochs"), (0.75, "loss stop improve after epoch 50 and early stop")],
            1.0,
            "50 epochs, because early stopping triggered when loss stopped improving.",
            "how many epochs was the model actually trained for before stopping?"
        ),
        (
            "all_caps_urgent",
            [(0.15, "REQUIREMENT: DATASET SPLIT IS 70% TRAIN, 15% VAL, 15% TEST!"), (0.70, "TOTAL RAW SAMPLES COLLECTED IS 10,000!")],
            1.0,
            "Train: 7,000 samples (70%), Val: 1,500 samples (15%), Test: 1,500 samples (15%).",
            "HOW MANY EXACT SAMPLES ARE ALLOCATED TO TRAIN, VAL, AND TEST RESPECTIVELY?"
        ),
        (
            "confused_beginner",
            [(0.15, "awalnya kita mau pake model BERT"), (0.75, "tapi dosen bilang ganti RoBERTa biar lebih modern")],
            1.0,
            "RoBERTa (menggantikan rencana awal BERT sesuai arahan dosen).",
            "model apa yang akhirnya kita pilih untuk eksperimen?"
        ),
        (
            "casual_slang",
            [(0.15, "aturan 1: diskon token 50% kalo query malem"), (0.80, "query dilakukan jam 11 malem")],
            1.0,
            "Dapat diskon 50%, karena query dilakukan pada jam 11 malam.",
            "apakah query saya berhak dapet diskon token?"
        ),
        (
            "terse_lowercase",
            [(0.10, "v1: top-k = 10"), (0.40, "v2: top-k increased to 25"), (0.80, "v3: final top-k set to 15")],
            1.0,
            "Final active top-k is 15 (superseded from 10 and 25).",
            "what is the final active top-k parameter after all updates?"
        ),
        (
            "academic_verbose",
            [(0.15, "Phase 1 requires unweighted cross-entropy loss."), (0.75, "Phase 2 fine-tuning introduces a focal penalty with gamma=2.0 and alpha=0.25.")],
            1.0,
            "Phase 1 uses standard cross-entropy; Phase 2 introduces focal penalty (gamma=2.0, alpha=0.25).",
            "How does the loss function formulation differ between Phase 1 and Phase 2?"
        ),
        (
            "broken_english",
            [(0.15, "we have 1000 dollar, cloud cost 10 dollar per hour"), (0.70, "training run 120 hour")],
            1.0,
            "No, budget will be exceeded: 120 hours x $10 = $1200, which exceeds the $1000 budget by $200.",
            "is our 1000 dollar budget enough to finish the 120 hour training?"
        ),
        (
            "all_caps_urgent",
            [(0.20, "CRITICAL: IF SENSITIVITY < 0.95, REJECT MODEL!"), (0.80, "RESULT: SENSITIVITY IS 0.962, SPECIFICITY IS 0.910!")],
            1.0,
            "Accept/Do not reject, because sensitivity is 0.962 which meets the >= 0.95 requirement.",
            "SHOULD WE ACCEPT OR REJECT THE MODEL BASED ON THE SENSITIVITY THRESHOLD?"
        ),
        (
            "confused_beginner",
            [(0.15, "file train.json ada 800 baris"), (0.70, "file test.json ada 200 baris")],
            1.0,
            "1.000 baris total (800 train + 200 test).",
            "berapa total seluruh baris data jika train dan test digabung?"
        ),
        (
            "casual_slang",
            [(0.15, "aturan lab: ga boleh ninggal server nyala lebih dr 48 jam"), (0.80, "training udah jalan 52 jam")],
            1.0,
            "Sudah melanggar aturan, karena training berjalan 52 jam (melebihi batas maksimal 48 jam).",
            "apakah status server saat ini melanggar aturan lab?"
        )
    ]

    for r_idx, (persona, needles_data, p_ratio, expected, probe) in enumerate(r_specs):
        load = loads[r_idx % len(loads)]
        needles = [{"input": n_text, "depth_ratio": d_ratio, "type": "reasoning", "persona": persona} for d_ratio, n_text in needles_data]
        cases.append({
            "id": f"R-NIAH-{r_idx+1:02d}",
            "tier": "r_niah",
            "token_load": load,
            "depth_ratio": needles_data[-1][0],
            "probe_ratio": p_ratio,
            "persona": persona,
            "target_documents": [test_papers[(r_idx + 10) % len(test_papers)]],
            "needles": needles,
            "expected_answer": expected,
            "probe_query": probe
        })

    # --------------------------------------------------------------------------
    # QUADRANT 4: 25 U-NIAH Cases (Negative Abstention Traps - Absent Information)
    # The needle contains fact X, but user probes fact Y (which was NEVER mentioned).
    # Expected Answer: AI MUST honestly state it was not mentioned!
    # --------------------------------------------------------------------------
    u_specs = [
        # (persona, load, depth, needle_given, probe_unmentioned)
        ("casual_slang", "4k", 0.30, "eh bro ram laptop gw cuma 8gb ya", "tadi gw ada sebut merk laptop gw gak ya? merk apa?"),
        ("terse_lowercase", "4k", 0.70, "batch size: 64", "what was the learning rate schedule specified earlier?"),
        ("academic_verbose", "8k", 0.20, "IRB ethics protocol #2026-B81 was approved.", "What was the grant funding dollar amount provided by the National Science Foundation?"),
        ("broken_english", "8k", 0.60, "we use adamw optimizer for train model", "what is the random seed number we use?"),
        ("all_caps_urgent", "8k", 0.85, "ALERT: RESAMPLE ALL AUDIO TO 16000HZ!", "WHAT WAS THE MONETARY HOURLY WAGE PAID TO THE AUDIO TRANSCRIBERS?"),
        ("confused_beginner", "16k", 0.25, "saya simpan modelnya di file best_weights.pt", "berapa ukuran file best_weights.pt dalam gigabyte yang saya sebutkan tadi?"),
        ("casual_slang", "16k", 0.50, "pembimbing gw nyuruh pake korpus multiun", "tadi pembimbing gw ada nyebut batas deadline pengumpulan tesis gak? kapan?"),
        ("terse_lowercase", "16k", 0.80, "dropout: 0.1", "what was the activation function specified?"),
        ("academic_verbose", "32k", 0.15, "The diagnostic cohort was recruited from Charité Berlin.", "What was the mean body mass index (BMI) of the clinical cohort?"),
        ("broken_english", "32k", 0.40, "our server has 16gb ram zero swap", "what is the ip address of our server?"),
        ("all_caps_urgent", "32k", 0.75, "CRITICAL: MAXIMUM CLUSTER RUNTIME IS CAPPED AT 72 GPU-HOURS!", "WHAT IS THE CLUSTER ELECTRICITY COST IN DOLLARS PER KILOWATT-HOUR?"),
        ("confused_beginner", "32k", 0.90, "loss function kita disuruh pake Dice Loss", "siapa nama dosen pembimbing yang nyuruh pake Dice Loss tadi min?"),
        ("casual_slang", "64k", 0.10, "gpu kita pake rtx 4090 vram 24gb ya bro", "tadi kita beli gpu rtx 4090 di toko komputer mana ya?"),
        ("terse_lowercase", "64k", 0.35, "quantization: 4-bit awq group size 128", "what was the temperature parameter for text generation?"),
        ("academic_verbose", "64k", 0.60, "Tissue biopsies were stained using standard hematoxylin and eosin protocols.", "What was the manufacturer catalog serial number of the microscope used?"),
        ("broken_english", "64k", 0.85, "we must use 10 fold cross validation", "how many hours each fold take to complete?"),
        ("all_caps_urgent", "16k", 0.30, "MANDATE: SUBMIT EXCLUSIVELY TO ACL 2026 CONFERENCE!", "WHAT IS THE EXACT PAGE LIMIT REQUIREMENT FOR SHORT PAPERS AT ACL 2026?"),
        ("confused_beginner", "32k", 0.20, "saya cuma punya koneksi internet 10 Mbps di kostan", "berapa biaya langganan wifi kostan saya per bulan yang saya sebutin tadi?"),
        ("casual_slang", "8k", 0.40, "token pooling wajib mean-pooling ya", "kenapa dosen kita gasuka sama CLS token? ada gw sebutin alasannya gak?"),
        ("terse_lowercase", "64k", 0.50, "metric: macro-f1 across minority classes", "what was the accuracy percentage score on the majority class?"),
        ("academic_verbose", "32k", 0.30, "The text backbone is RoBERTa-large with 355M parameters.", "What was the pre-training carbon footprint in metric tons of CO2 equivalent?"),
        ("broken_english", "16k", 0.60, "we use bpe tokenizer vocabulary 32000", "how many days tokenizer take to train on raw corpus?"),
        ("all_caps_urgent", "64k", 0.20, "INVARIANT: NEVER STORE PLAINTEXT PASSWORDS IN REDIS!", "WHAT ENCRYPTION ALGORITHM (AES-256 OR RSA) WAS MANDATED FOR PASSWORDS?"),
        ("confused_beginner", "8k", 0.70, "min saya pake laptop windows 11 home edition", "tadi saya sebut processor laptop saya intel core i5 atau i7 ya?"),
        ("casual_slang", "4k", 0.80, "lisensi repo kita apache 2.0 ya", "siapa nama pengacara hak cipta yang nyaranin lisensi apache tadi?")
    ]

    for u_idx, (persona, load, depth, needle_given, probe_q) in enumerate(u_specs):
        cases.append({
            "id": f"U-NIAH-{u_idx+1:02d}",
            "tier": "u_niah",
            "token_load": load,
            "depth_ratio": depth,
            "probe_ratio": 1.0,
            "persona": persona,
            "target_documents": [test_papers[(u_idx + 15) % len(test_papers)]],
            "needles": [
                {
                    "input": needle_given,
                    "depth_ratio": depth,
                    "type": "negative_trap",
                    "persona": persona
                }
            ],
            "expected_answer": "Unmentioned/Absent. The requested information was never stated, specified, or mentioned in our conversation.",
            "probe_query": probe_q
        })

    assert len(cases) == 100, f"Expected 100 cases, got {len(cases)}"
    return cases


def generate_val_25_cases() -> List[Dict[str, Any]]:
    """Generates a balanced 25-case held-out validation matrix: 7 S-NIAH, 6 M-NIAH, 6 R-NIAH, 6 U-NIAH."""
    cases: List[Dict[str, Any]] = []

    # 1. 7 S-NIAH Cases
    s_val = [
        ("casual_slang", "4k", 0.10, "eh min, protokol etik penelitian kita pake nomer IRB #2026-B81 ya", "Protokol etik IRB #2026-B81.", "apa nomor protokol etik irb yang saya sebut tadi?"),
        ("terse_lowercase", "4k", 0.90, "max compute: 72 gpu-hours runtime capped", "Max compute is 72 GPU-hours.", "what was the compute runtime cap?"),
        ("academic_verbose", "8k", 0.30, "Patient de-identification must strictly conform to the HIPAA Safe Harbor standard.", "HIPAA Safe Harbor standard.", "Which patient de-identification standard was mandated?"),
        ("broken_english", "8k", 0.70, "fix adamw weight decay to 0.015 with cosine annealing", "AdamW weight decay 0.015 with cosine annealing.", "what weight decay value did i specify?"),
        ("all_caps_urgent", "16k", 0.10, "MANDATE: APACHE 2.0 LICENSE ONLY, STRICTLY NEVER USE GPL!", "Apache 2.0 license (strictly never GPL).", "WHAT OPEN SOURCE LICENSE WAS SPECIFIED?"),
        ("confused_beginner", "32k", 0.50, "saya cuma ngerti apple silicon mps, jangan pake cuda ya min", "Apple Silicon Metal (MPS backend only, no CUDA).", "hardware apa yang saya minta gunakan tadi?"),
        ("terse_lowercase", "64k", 0.70, "quantization: 8-bit gptq act-order group size 64", "8-bit GPTQ with act-order and group size 64.", "what quantization format and group size did i set in validation?")
    ]

    for idx, (persona, load, depth, needle, expected, probe) in enumerate(s_val):
        cases.append({
            "id": f"S-VAL-{idx+1:02d}",
            "tier": "s_niah",
            "token_load": load,
            "depth_ratio": depth,
            "probe_ratio": 1.0,
            "persona": persona,
            "target_documents": [val_papers[idx % len(val_papers)]],
            "needles": [{"input": needle, "depth_ratio": depth, "type": "directive", "persona": persona}],
            "expected_answer": expected,
            "probe_query": probe
        })

    # 2. 6 M-NIAH Cases
    m_val = [
        ("casual_slang", "8k", [(0.15, "sampling audio diset 16000hz ya"), (0.75, "mel channel pake 80")], 1.0, "Sampling rate 16000Hz dan mel channels 80.", "berapa nilai sampling rate dan mel channel tadi?"),
        ("terse_lowercase", "16k", [(0.20, "checkpoint step: 2500"), (0.45, "warmup: 1000"), (0.80, "lr: 3e-4")], 1.0, "Checkpoint interval 2500 steps, warmup 1000, peak lr 3e-4.", "what are checkpoint step, warmup, and lr?"),
        ("academic_verbose", "16k", [(0.15, "Trial eligibility requires minimum age of 45 years."), (0.40, "Exclude participants with immunosuppressant therapy within 12 months.")], 0.60, # Mid probe!
         "Minimum age 45 years and exclusion of immunosuppressants within 12 months.", "What were the clinical trial inclusion age and medication exclusion rules?"),
        ("broken_english", "32k", [(0.20, "reserve 15 percent data for ood test"), (0.75, "seed is 777")], 1.0, "15% data reserved for OOD test with random seed 777.", "what percentage for ood test and what seed?"),
        ("all_caps_urgent", "32k", [(0.15, "BACKBONE: ROBERTA-LARGE 355M PARAMETERS!"), (0.80, "POOLING: MEAN-POOLING ONLY, FORBID CLS!")], 1.0, "RoBERTa-large (355M parameters) with mean-pooling only.", "WHAT ENCODER BACKBONE AND POOLING METHOD WAS MANDATED?"),
        ("confused_beginner", "64k", [(0.10, "port redisnya 6389 min"), (0.85, "terus ttl-nya 86400 detik 24 jam")], 1.0, "Port Redis 6389 dan TTL 86400 detik (24 jam).", "berapa port redis dan ttl cache yang saya sebut tadi?")
    ]

    for idx, (persona, load, needles_data, p_ratio, expected, probe) in enumerate(m_val):
        needles = [{"input": n_text, "depth_ratio": d_ratio, "type": "multi", "persona": persona} for d_ratio, n_text in needles_data]
        cases.append({
            "id": f"M-VAL-{idx+1:02d}",
            "tier": "m_niah",
            "token_load": load,
            "depth_ratio": needles_data[-1][0],
            "probe_ratio": p_ratio,
            "persona": persona,
            "target_documents": [val_papers[(idx + 2) % len(val_papers)]],
            "needles": needles,
            "expected_answer": expected,
            "probe_query": probe
        })

    # 3. 6 R-NIAH Cases
    r_val = [
        ("casual_slang", "8k", [(0.20, "edge device kita memori ram-nya cuma 8gb ya"), (0.75, "model fp16 butuh 14GB, kalo 4-bit quant cuma butuh 5GB")], 1.0,
         "Tidak bisa jalan di FP16 (8GB < 14GB), tapi bisa jalan di 4-bit quant (5GB <= 8GB).", "bisa gak edge device kita jalanin model ini di FP16 dan di 4-bit quant?"),
        ("terse_lowercase", "16k", [(0.15, "v1 policy: 50 epochs, batch 32"), (0.80, "superseding v2 policy: epochs halved to 25, batch doubled to 64")], 1.0,
         "Under v2 policy: 25 epochs and batch size 64.", "what are the active epoch count and batch size under v2 policy?"),
        ("academic_verbose", "16k", [(0.15, "Condition: If validation loss plateaus for 3 epochs, reduce learning rate by 50%."), (0.80, "Epochs 12, 13, and 14 plateaued at loss 1.84 with zero progress.")], 1.0,
         "Yes, reduce learning rate by 50% because loss plateaued for 3 consecutive epochs.", "Should the learning rate reduction be triggered based on our condition?"),
        ("broken_english", "32k", [(0.20, "rule: reject study before year 2015"), (0.75, "study cohort gamma published in 2011")], 1.0,
         "Excluded/rejected because it was published in 2011 which is before 2015.", "can we include study cohort gamma in meta-analysis?"),
        ("all_caps_urgent", "32k", [(0.15, "PIPELINE MODULE 2 STRICTLY EXPECTS TENSORS IN B X C X T AUDIO LAYOUT!"), (0.75, "STAGE 1 ACOUSTIC BACKBONE OUTPUTS TENSORS IN T X B X C LAYOUT!")], 1.0,
         "No, tensor permutation from T x B x C to B x C x T is required before Module 2 can consume the output.", "CAN MODULE 2 DIRECTLY CONSUME STAGE 1 OUTPUT WITHOUT PERMUTATION?"),
        ("confused_beginner", "64k", [(0.15, "kata dosen harus minimal dapet gain 2.5 BLEU dari baseline"), (0.80, "hasilnya: baseline 31.2 BLEU, model kita 34.1 BLEU")], 1.0,
         "Boleh/layak digunakan karena gain-nya 2.9 BLEU (34.1 - 31.2), melebihi syarat minimal 2.5 BLEU.", "apakah hasil model kita layak digunakan menurut arahan dosen tadi?")
    ]

    for idx, (persona, load, needles_data, p_ratio, expected, probe) in enumerate(r_val):
        needles = [{"input": n_text, "depth_ratio": d_ratio, "type": "reasoning", "persona": persona} for d_ratio, n_text in needles_data]
        cases.append({
            "id": f"R-VAL-{idx+1:02d}",
            "tier": "r_niah",
            "token_load": load,
            "depth_ratio": needles_data[-1][0],
            "probe_ratio": p_ratio,
            "persona": persona,
            "target_documents": [val_papers[(idx + 4) % len(val_papers)]],
            "needles": needles,
            "expected_answer": expected,
            "probe_query": probe
        })

    # 4. 6 U-NIAH Cases (Negative Abstention Traps)
    u_val = [
        ("casual_slang", "4k", 0.25, "eh laptop gw cuma punya ram 8gb ya min", "tadi gw ada bilang merk processor laptop gw intel atau amd gak ya?"),
        ("terse_lowercase", "8k", 0.70, "micro batch size: 16", "what was the gradient accumulation steps number specified earlier?"),
        ("academic_verbose", "16k", 0.30, "IRB protocol #2026-B81 was formally approved.", "What was the grant funding dollar amount provided by the university?"),
        ("broken_english", "32k", 0.50, "we use adamw optimizer with cosine decay", "what was the numpy random state integer initialized earlier?"),
        ("all_caps_urgent", "64k", 0.20, "ALERT: RESAMPLE AUDIO TO 16000HZ!", "WHAT WAS THE MONETARY HOURLY WAGE PAID TO AUDIO RECORDING ACTORS?"),
        ("confused_beginner", "16k", 0.80, "saya simpan modelnya di best_model.pt", "berapa ukuran file best_model.pt dalam gigabyte yang tadi saya sebutin min?")
    ]

    for idx, (persona, load, depth, needle, probe) in enumerate(u_val):
        cases.append({
            "id": f"U-VAL-{idx+1:02d}",
            "tier": "u_niah",
            "token_load": load,
            "depth_ratio": depth,
            "probe_ratio": 1.0,
            "persona": persona,
            "target_documents": [val_papers[(idx + 6) % len(val_papers)]],
            "needles": [{"input": needle, "depth_ratio": depth, "type": "negative_trap", "persona": persona}],
            "expected_answer": "Unmentioned/Absent. The requested information was never stated, specified, or mentioned in our conversation.",
            "probe_query": probe
        })

    assert len(cases) == 25, f"Expected 25 cases, got {len(cases)}"
    return cases


def main():
    test_100 = generate_test_100_cases()
    with open(TEST_100_PATH, "w", encoding="utf-8") as f:
        json.dump(test_100, f, indent=2)
    print(f"✓ Saved 100-case Protocol B Test Matrix to: {TEST_100_PATH}")

    val_25 = generate_val_25_cases()
    with open(VAL_25_PATH, "w", encoding="utf-8") as f:
        json.dump(val_25, f, indent=2)
    print(f"✓ Saved 25-case Protocol B Val Matrix to: {VAL_25_PATH}")

    # Anti-leakage audit between Val-25 and Test-100
    val_needles = set(n["input"].strip().lower() for c in val_25 for n in c["needles"])
    val_probes = set(c["probe_query"].strip().lower() for c in val_25)

    test_needles = set(n["input"].strip().lower() for c in test_100 for n in c["needles"])
    test_probes = set(c["probe_query"].strip().lower() for c in test_100)

    needle_overlap = val_needles.intersection(test_needles)
    assert len(needle_overlap) == 0, f"DATA LEAKAGE DETECTED! Overlapping needles: {needle_overlap}"

    probe_overlap = val_probes.intersection(test_probes)
    assert len(probe_overlap) == 0, f"DATA LEAKAGE DETECTED! Overlapping probes: {probe_overlap}"

    print("✓ Anti-Leakage Audit PASSED: 0 needle overlaps, 0 probe overlaps between Val-25 and Test-100!")


if __name__ == "__main__":
    main()
