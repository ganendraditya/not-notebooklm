# Not-NotebookLM Dual-Cap Conversational NIAH Benchmark Report (25-CASE HELD-OUT VALIDATION)
*Multi-Spectral Needle-In-A-Haystack Evaluation across S-NIAH, M-NIAH, and R-NIAH (Stanford RULER & Anthropic Standards)*

- **Split**: `val`
- **Total Cases Evaluated**: 25 Cases
- **Mode A (8K Cap / Compaction)**: `0.960` overall accuracy
- **Mode B (1M Native Ingestion)**: `1.000` overall accuracy

## 1. Multi-Spectral Scorecard
| Evaluation Spectrum | Mode A (8K Cap / Compaction) | Mode B (1M Native Ingestion) |
| :--- | :---: | :---: |
| **Overall Needle Accuracy** | **`0.960`** | **`1.000`** |
| **S_NIAH Fidelity** | `0.857` | `1.000` |
| **M_NIAH Fidelity** | `1.000` | `1.000` |
| **R_NIAH Fidelity** | `1.000` | `1.000` |
| **U_NIAH Abstention Fidelity** | `1.000` | `1.000` |

## 2. 2D Accuracy Heatmap Grids (Token Load vs. Depth Tier)
### Mode A: 8K Context Cap (Token Waterfall & Smart History Compaction)
```text
┌─────────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│ Depth \ Tokens  │    4K    │    8K    │   16K    │   32K    │  64K-100K│
├─────────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ 10% (Top)       │  1.000   │   N/A    │  0.000   │   N/A    │   N/A    │
│ 30% (Early)     │   N/A    │  1.000   │   N/A    │   N/A    │   N/A    │
│ 50% (Middle)    │   N/A    │   N/A    │   N/A    │  1.000   │   N/A    │
│ 70% (Late)      │   N/A    │  1.000   │   N/A    │   N/A    │  1.000   │
│ 90% (Recency)   │  1.000   │   N/A    │   N/A    │   N/A    │   N/A    │
└─────────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
```
### Mode B: 1M Context Cap (Frontier Native Long-Context Ingestion)
```text
┌─────────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│ Depth \ Tokens  │    4K    │    8K    │   16K    │   32K    │  64K-100K│
├─────────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ 10% (Top)       │  1.000   │   N/A    │  1.000   │   N/A    │   N/A    │
│ 30% (Early)     │   N/A    │  1.000   │   N/A    │   N/A    │   N/A    │
│ 50% (Middle)    │   N/A    │   N/A    │   N/A    │  1.000   │   N/A    │
│ 70% (Late)      │   N/A    │  1.000   │   N/A    │   N/A    │  1.000   │
│ 90% (Recency)   │  1.000   │   N/A    │   N/A    │   N/A    │   N/A    │
└─────────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
```
### Mode B: 1M Context Cap (Frontier Native Long-Context Ingestion)
```text
┌─────────────────┬──────────┬──────────┬──────────┬──────────┬──────────┐
│ Depth \ Tokens  │    4K    │    8K    │   16K    │   32K    │  64K-100K│
├─────────────────┼──────────┼──────────┼──────────┼──────────┼──────────┤
│ 10% (Top)       │   N/A    │   N/A    │   N/A    │   N/A    │   N/A    │
│ 30% (Early)     │   N/A    │   N/A    │   N/A    │   N/A    │   N/A    │
│ 50% (Middle)    │   N/A    │   N/A    │   N/A    │   N/A    │   N/A    │
│ 70% (Late)      │   N/A    │   N/A    │   N/A    │   N/A    │   N/A    │
│ 90% (Recency)   │   N/A    │   N/A    │   N/A    │   N/A    │   N/A    │
└─────────────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
```