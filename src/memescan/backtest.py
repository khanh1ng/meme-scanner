"""Portfolio backtest: next-open entry, intraday stops, square-root impact costs, daily mark to market.

Two modes.
* legacy=True reproduces the research notebook (archive/notebooks/04_scanner_v2_pit.ipynb) exactly.
  It has two defects found while building this package:
  1. the solvency check adds each trade's FINAL P&L to equity when the trade is opened, so the
     decision "is there capital left for another position" uses results that have not happened yet;
  2. the daily equity curve marks positions close-to-close from the entry day's close and values the
     exit day at its close, so it ignores the entry day (open to close) and stop fills. Sharpe and
     drawdown were computed on that curve while final equity came from trade P&L.
* legacy=False (default) fixes both: solvency uses only trades closed before the decision day, and the
  curve marks open->close on entry, close->close while held, and prev close->exit price on exit,
  so the curve ends exactly at capital + total net P&L.
"""
from collections import defaultdict

import numpy as np
import pandas as pd

from . import config as C
from .panel import atr


def cost_one_way(alloc, adv):
    """Square-root market impact plus a fixed spread, capped. Never validated against real fills."""
    if not np.isfinite(adv) or adv <= 0:
        return C.COST_CAP
    return min(C.COST_CAP, C.COST_FIXED + C.COST_IMPACT * np.sqrt(alloc / adv))


def _arrays(p):
    out = {}
    for s in p.tickers:
        h = np.nan_to_num(p.high[s].values.astype("float64"))
        l_ = np.nan_to_num(p.low[s].values.astype("float64"))
        c0 = np.nan_to_num(p.close[s].values.astype("float64"))
        out[s] = {"c": p.close[s].values.astype("float64"), "o": p.open[s].values.astype("float64"),
                  "l": p.low[s].values.astype("float64"), "atr": atr(h, l_, c0)}
    return out


def _exit(a, ei):
    """Walk forward from the entry bar. Order matters: a gap through the stop is checked before an
    intraday touch, because an opening gap fills at the open, not at the stop."""
    c, o, l, at = a["c"], a["o"], a["l"], a["atr"]
    e = o[ei]
    peak, xi, ex, why = e, min(ei + C.MAX_HOLD, len(c) - 1), None, "max_hold"
    for j in range(ei + 1, xi + 1):
        if np.isnan(c[j]):
            continue
        stop = e * (1 - C.HARD_STOP)
        if o[j] <= stop:
            return j, o[j], "stop_gap"
        if l[j] <= stop:
            return j, stop, "stop"
        if (j - ei) >= C.EARLY_DAYS and (np.nanmax(c[ei + 1:j + 1]) / e - 1) < C.EARLY_MFE:
            return j, c[j], "no_progress"
        peak = max(peak, c[j])
        if c[j] <= peak - C.ATR_MULT * (at[j] if not np.isnan(at[j]) else 0):
            return j, c[j], "atr_trail"
        if c[j] > e and c[j] < np.nanmean(c[max(0, j - C.MA_EXIT + 1):j + 1]):
            return j, c[j], "trend_break"
    if ex is None or np.isnan(ex):
        ex = c[xi]
    return xi, ex, why


def run(p, sig, dv20, use_cost=True, legacy=False):
    """sig: {date: [(score, ticker)]} decided at the close of date; entry at the next open."""
    dates = p.dates
    dix = {d: i for i, d in enumerate(dates)}
    arr = _arrays(p)
    trades, open_until = [], []
    legacy_equity = C.CAPITAL
    for d in dates:
        if d not in sig:
            continue
        i0 = dix[d]
        closed_pnl = sum(t["pnl"] for t in trades if t["exit_date"] < d)
        for score, s in sorted(sig[d], reverse=True):
            open_until = [x for x in open_until if x > d]
            if len(open_until) >= C.MAX_POS:
                break
            equity_now = legacy_equity if legacy else C.CAPITAL + closed_pnl
            if equity_now < C.POS_SIZE:          # halt new entries when capital is gone
                break
            a = arr[s]
            ei = i0 + 1
            if ei >= len(a["c"]) or np.isnan(a["o"][ei]) or a["o"][ei] <= 0:
                continue
            xi, ex, why = _exit(a, ei)
            e = a["o"][ei]
            gross = ex / e - 1
            cst = 2 * cost_one_way(C.POS_SIZE, float(dv20.at[d, s])) if use_cost else 0.0
            legacy_equity += C.POS_SIZE * (gross - cst)
            open_until.append(dates[xi])
            trades.append({"ticker": s, "signal_date": d, "ei": ei, "xi": xi,
                           "entry_date": dates[ei], "exit_date": dates[xi],
                           "entry_px": e, "exit_px": ex, "gross": gross, "cost": cst,
                           "ret": gross - cst, "pnl": C.POS_SIZE * (gross - cst),
                           "days": xi - ei, "exit_reason": why})
    tk = pd.DataFrame(trades)
    if tk.empty:
        return tk, None
    return tk, equity_curve(tk, arr, dates, legacy)


def equity_curve(tk, arr, dates, legacy=False):
    acc = defaultdict(float)
    for t in tk.itertuples():
        c, o = arr[t.ticker]["c"], arr[t.ticker]["o"]
        sh = C.POS_SIZE / t.entry_px
        if legacy:
            for j in range(t.ei + 1, t.xi + 1):
                if not np.isnan(c[j]) and not np.isnan(c[j - 1]):
                    acc[dates[j]] += sh * (c[j] - c[j - 1])
        else:
            last = o[t.ei]
            for j in range(t.ei, t.xi + 1):
                px = t.exit_px if j == t.xi else c[j]
                if np.isnan(px):
                    continue
                acc[dates[j]] += sh * (px - last)
                last = px
        acc[t.exit_date] -= C.POS_SIZE * t.cost
    return C.CAPITAL + pd.Series([acc.get(d, 0.0) for d in dates], index=dates).cumsum()


def stats(tk, eq, dates):
    r = eq.pct_change().dropna()
    yrs = (dates[-1] - dates[0]).days / 365.25
    down = r[r < 0]
    final = C.CAPITAL + tk.pnl.sum()
    top10 = tk.nlargest(10, "pnl").pnl.sum()
    return {"n": len(tk), "win": (tk.ret > 0).mean(), "exp": tk.ret.mean(), "cost": tk.cost.mean(),
            "pnl": tk.pnl.sum(), "final": final,
            "cagr": (final / C.CAPITAL) ** (1 / yrs) - 1 if final > 0 else -1.0,
            "sharpe": r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan,
            "sortino": r.mean() / down.std() * np.sqrt(252) if len(down) and down.std() > 0 else np.nan,
            "maxdd": ((eq - eq.cummax()) / eq.cummax().clip(lower=1)).min(),
            "pnl_ex_top10": tk.pnl.sum() - top10,
            "curve_end_minus_final": float(eq.iloc[-1] - final)}
