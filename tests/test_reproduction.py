"""The ported engine reproduces the research notebook. Reference values are copied from the
notebook's saved output (archive/notebooks/06_scanner_v2_pit.ipynb, v2_final_comparison.csv).
Skipped when results/backtest_summary.csv has not been generated."""
from pathlib import Path

import pandas as pd
import pytest

SUMMARY = Path(__file__).resolve().parents[1] / "results" / "backtest_summary.csv"
NOTEBOOK = {   # universe: (trades, final equity, sharpe, max drawdown)
    "PIT universe": (790, 9465.870427538219, -0.1882959324884652, -0.6399257028494862),
    "Hindsight 82, same filter (ceiling)": (1207, 247310.06687554286, 0.5295532753286443, -0.49194191660698616),
    "Random names, same filter (floor)": (883, 9532.278143798394, -0.5952442564684568, -0.5928456740853362),
}


@pytest.mark.skipif(not SUMMARY.exists(), reason="run scripts/run_backtest.py first")
def test_legacy_engine_matches_the_notebook():
    df = pd.read_csv(SUMMARY)
    leg = df[df.engine == "legacy"].set_index("universe")
    for name, (n, final, sharpe, maxdd) in NOTEBOOK.items():
        row = leg.loc[name]
        assert row.n == n
        assert row.final == pytest.approx(final, rel=1e-9)
        assert row.sharpe == pytest.approx(sharpe, rel=1e-9)
        assert row.maxdd == pytest.approx(maxdd, rel=1e-9)


@pytest.mark.skipif(not SUMMARY.exists(), reason="run scripts/run_backtest.py first")
def test_corrected_curve_matches_realised_pnl():
    df = pd.read_csv(SUMMARY)
    assert (df[df.engine == "corrected"].curve_end_minus_final.abs() < 1e-3).all()
