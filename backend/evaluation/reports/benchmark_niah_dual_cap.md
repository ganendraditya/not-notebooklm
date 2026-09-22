# Not-NotebookLM Dual-Cap Conversational NIAH Benchmark Report (100-CASE COMPREHENSIVE TEST)
*Multi-Spectral Needle-In-A-Haystack Evaluation across S-NIAH, M-NIAH, and R-NIAH (Stanford RULER & Anthropic Standards)*

- **Split**: `test`
- **Total Cases Evaluated**: 100 Cases
- **Mode A (8K Cap / Compaction)**: `0.980` overall accuracy
- **Mode B (1M Native Ingestion)**: `0.950` overall accuracy

## 1. Multi-Spectral Scorecard
| Evaluation Spectrum | Mode A (8K Cap / Compaction) | Mode B (1M Native Ingestion) |
| :--- | :---: | :---: |
| **Overall Needle Accuracy** | **`0.980`** | **`0.950`** |
| **S_NIAH Fidelity** | `0.960` | `0.920` |
| **M_NIAH Fidelity** | `1.000` | `1.000` |
| **R_NIAH Fidelity** | `1.000` | `0.960` |
| **U_NIAH Abstention Fidelity** | `0.960` | `0.920` |

## 2. 2D Accuracy Heatmap Grids (Token Load vs. Depth Tier)
### Mode A: 8K Context Cap (Token Waterfall & Smart History Compaction)
```text
┌─────────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│ Depth \ Tokens  │    4K    │    8K    │   16K    │   32K    │  64K-100K│
├─────────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ 10% (Top)       │  1.000   │  1.000   │  1.000   │  1.000   │  1.000   │
│ 30% (Early)     │  1.000   │  1.000   │  1.000   │  1.000   │  1.000   │
│ 50% (Middle)    │  1.000   │  1.000   │  1.000   │  1.000   │  1.000   │
│ 70% (Late)      │  0.000   │  1.000   │  1.000   │  1.000   │  1.000   │
│ 90% (Recency)   │  1.000   │  1.000   │  1.000   │  1.000   │  1.000   │
└─────────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
```
### Mode B: 1M Context Cap (Frontier Native Long-Context Ingestion)
```text
┌─────────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│ Depth \ Tokens  │    4K    │    8K    │   16K    │   32K    │  64K-100K│
├─────────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ 10% (Top)       │  1.000   │  1.000   │  1.000   │  1.000   │  1.000   │
│ 30% (Early)     │  0.000   │  1.000   │  1.000   │  1.000   │  1.000   │
│ 50% (Middle)    │  1.000   │  1.000   │  1.000   │  1.000   │  1.000   │
│ 70% (Late)      │  0.000   │  1.000   │  1.000   │  1.000   │  1.000   │
│ 90% (Recency)   │  1.000   │  1.000   │  1.000   │  1.000   │  1.000   │
└─────────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
```