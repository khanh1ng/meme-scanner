# Archive

The original research notebooks and scripts, in the order they were written. Credentials were
removed and outputs cleared; nothing else was changed. Defect numbers refer to
`docs/RESEARCH_LOG.md` and list only those verified in each file's code. They are kept as the record of how the
defects in `docs/RESEARCH_LOG.md` were found, not as working code. The maintained implementation is
`src/memescan/`.

| File | Stage | Universe | Known defects |
|---|---|---|---|
| `notebooks/01_squeeze_scanner.ipynb` | v0: full live pipeline, backtest, event study | 82 names listed by a language model | 1, 7, 9 |
| `notebooks/02_entry_absorption.ipynb` | v0: absorption entry | same | 1, 7, 9 |
| `notebooks/03_scanner_v1_lean.ipynb` | v1: two-layer scanner, LLM out of the decision path | same | 1, 7, 9; 4, 14 and 16 found and fixed here |
| `notebooks/04_compare_universe_versions.ipynb` | v1 audit: point-in-time screens, IC first | survivor pool | 9, no costs |
| `notebooks/05_v1_pit_second_try.ipynb` | v1 audit | survivor pool | 9, 11 (found here) |
| `notebooks/06_scanner_v2_pit.ipynb` | v2 | all surviving US stocks, costs | 9, 18, 19 |
| `scripts/*.py` | data fetchers and the comparison script used by the notebooks | | |
