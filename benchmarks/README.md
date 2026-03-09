# Benchmarks

Benchmark suites evaluating Contract-AF against established legal contract analysis datasets.

## Benchmarks

### CUAD (Contract Understanding Atticus Dataset)

Clause-type-level evaluation against 25 annotated clause categories from the CUAD v1 dataset.

- **Comparison report**: [`cuad/COMPARISON.md`](cuad/COMPARISON.md) — detailed clause-by-clause analysis
- **Results**: [`cuad/results/`](cuad/results/) — JSON outputs from different model runs

```bash
# Run the CUAD benchmark against a Contract-AF result
python3 benchmarks/cuad/benchmark_cuad.py benchmarks/cuad/results/result_kimi-k2.5.json
```

### MAUD (Merger Agreement Understanding Dataset)

Question-level accuracy evaluation against 45+ M&A due diligence questions from the MAUD dataset.

- **Comparison report**: [`maud/COMPARISON.md`](maud/COMPARISON.md) — question-by-question analysis
- **LLM Judge evaluation**: [`maud/LLM_JUDGE.md`](maud/LLM_JUDGE.md) — Claude Opus 4 judge evaluation
- **Ground truth**: [`maud/contract_63_ground_truth.json`](maud/contract_63_ground_truth.json)
- **Results**: [`maud/results/`](maud/results/) — JSON outputs from different model runs

```bash
# Run the MAUD benchmark (single result)
python3 benchmarks/maud/benchmark_maud.py benchmarks/maud/results/result_kimi_v2.json

# Compare multiple results side-by-side
python3 benchmarks/maud/benchmark_maud.py benchmarks/maud/results/result_kimi_v2.json benchmarks/maud/results/result_gemini.json
```

> **Note**: The MAUD dataset itself is not included in this repo (it's ~150MB). Download it from [the MAUD repository](https://github.com/TheAtticusProject/maud) if you want to run Contract-AF against additional MAUD contracts.

### Unfair Terms of Service (CLAUDETTE / LexGLUE)

Evaluation against the CLAUDETTE and LexGLUE unfair ToS detection benchmarks.

- **Comparison report**: [`unfair_tos/COMPARISON.md`](unfair_tos/COMPARISON.md) — clause-level analysis
- **Test documents**: [`unfair_tos/documents.json`](unfair_tos/documents.json)
- **Results**: [`unfair_tos/results/`](unfair_tos/results/)

## Analysis Scripts

Utility scripts for extracting and comparing benchmark results:

| Script | Description |
|---|---|
| [`scripts/extract_comparison.py`](scripts/extract_comparison.py) | Extract and compare a single CUAD result against ground truth |
| [`scripts/extract_comparison_dual.py`](scripts/extract_comparison_dual.py) | Side-by-side comparison of two model runs (Kimi vs Gemini by default) |

```bash
# Single-model extraction
python3 benchmarks/scripts/extract_comparison.py benchmarks/cuad/results/result_kimi-k2.5.json

# Dual-model comparison
python3 benchmarks/scripts/extract_comparison_dual.py
```

## Directory Structure

```
benchmarks/
├── README.md
├── cuad/
│   ├── COMPARISON.md
│   ├── benchmark_cuad.py
│   └── results/
├── maud/
│   ├── COMPARISON.md
│   ├── LLM_JUDGE.md
│   ├── benchmark_maud.py
│   ├── contract_63_ground_truth.json
│   └── results/
├── unfair_tos/
│   ├── COMPARISON.md
│   ├── documents.json
│   └── results/
└── scripts/
    ├── extract_comparison.py
    └── extract_comparison_dual.py
```
