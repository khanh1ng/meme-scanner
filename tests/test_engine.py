"""Hand-checked mechanics of the backtest engine on tiny panels."""
import numpy as np
import pandas as pd
import pytest

from memescan import backtest, config as C
from memescan.panel import Panel


def _panel(o, h, l_, c, ticker="X"):
    idx = pd.bdate_range("2021-01-04", periods=len(c))
    f = lambda a, t="float32": pd.DataFrame({ticker: a}, index=idx).astype(t)  # noqa: E731
    return Panel(f(o), f(h), f(l_), f(c), f(np.full(len(c), 1e6), "float64"))


def _dv(p, value=1e9):
    return pd.DataFrame(value, index=p.close.index, columns=p.close.columns)


def test_entry_at_next_open_and_gap_stop_fills_at_open():
    n = 30
    c = np.full(n, 10.0); o = c.copy(); h = c * 1.01; l_ = c * 0.99
    o[1] = 10.0                      # entry at the open after the signal day
    o[2], c[2], h[2], l_[2] = 8.0, 8.0, 8.1, 7.9   # gaps through the 8% stop (9.2)
    p = _panel(o, h, l_, c)
    tk, eq = backtest.run(p, {p.dates[0]: [(5.0, "X")]}, _dv(p), use_cost=False)
    t = tk.iloc[0]
    assert t.entry_date == p.dates[1] and t.entry_px == 10.0
    assert t.exit_reason == "stop_gap" and t.exit_px == 8.0
    assert eq.iloc[-1] == pytest.approx(C.CAPITAL + t.pnl)


def test_intraday_stop_fills_at_stop_level():
    n = 30
    c = np.full(n, 10.0); o = c.copy(); h = c * 1.01; l_ = c * 0.99
    l_[2] = 9.0                      # touches the stop intraday, opens above it
    p = _panel(o, h, l_, c)
    tk, _ = backtest.run(p, {p.dates[0]: [(5.0, "X")]}, _dv(p), use_cost=False)
    assert tk.iloc[0].exit_reason == "stop"
    assert tk.iloc[0].exit_px == pytest.approx(10.0 * (1 - C.HARD_STOP))


def test_costs_are_charged_round_trip():
    adv = 2_000_000.0
    one_way = min(C.COST_CAP, C.COST_FIXED + C.COST_IMPACT * np.sqrt(C.POS_SIZE / adv))
    assert backtest.cost_one_way(C.POS_SIZE, adv) == pytest.approx(one_way)
    n = 30
    c = np.full(n, 10.0); p = _panel(c.copy(), c * 1.01, c * 0.99, c)
    tk, _ = backtest.run(p, {p.dates[0]: [(5.0, "X")]}, _dv(p, adv), use_cost=True)
    assert tk.iloc[0].cost == pytest.approx(2 * one_way)


def test_corrected_curve_ends_at_capital_plus_pnl_legacy_does_not():
    rng = np.random.default_rng(3)
    n = 120
    c = 10 * np.exp(np.cumsum(rng.normal(0.004, 0.03, n)))
    o = c * np.exp(rng.normal(0, 0.02, n)); h = np.maximum(o, c) * 1.02; l_ = np.minimum(o, c) * 0.98
    p = _panel(o, h, l_, c)
    sig = {p.dates[i]: [(3.0, "X")] for i in (5, 40, 80)}
    tk, eq = backtest.run(p, sig, _dv(p), legacy=False)
    assert eq.iloc[-1] == pytest.approx(C.CAPITAL + tk.pnl.sum(), abs=1e-6)
    tk_l, eq_l = backtest.run(p, sig, _dv(p), legacy=True)
    assert abs(eq_l.iloc[-1] - (C.CAPITAL + tk_l.pnl.sum())) > 1.0


def test_legacy_solvency_uses_future_pnl():
    """Two signals on the same day. The first trade will eventually lose everything; the legacy
    engine counts that loss at entry and refuses the second trade, the corrected one does not."""
    n = 40
    idx = pd.bdate_range("2021-01-04", periods=n)
    a = np.full(n, 10.0); b = np.full(n, 10.0)
    a[2:] = 0.01                      # name A collapses the day after entry
    oa = a.copy(); oa[1] = 10.0
    def frame(x, y, t="float32"):
        return pd.DataFrame({"A": x, "B": y}, index=idx).astype(t)
    p = Panel(frame(oa, b), frame(np.maximum(oa, a) * 1.01, b * 1.01), frame(np.minimum(oa, a) * 0.99, b * 0.99),
              frame(a, b), frame(np.full(n, 1e6), np.full(n, 1e6), "float64"))
    old_cap = C.CAPITAL
    C.CAPITAL = C.POS_SIZE          # exactly one position of capital
    try:
        sig = {p.dates[0]: [(9.0, "A"), (1.0, "B")]}
        assert len(backtest.run(p, sig, _dv(p), use_cost=False, legacy=True)[0]) == 1
        assert len(backtest.run(p, sig, _dv(p), use_cost=False, legacy=False)[0]) == 2
    finally:
        C.CAPITAL = old_cap
