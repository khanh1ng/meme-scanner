"""Layers 0 and 1: tradability and the point-in-time universe.

Every input to the universe for day t is known at the end of day t-1. Only ratios are used, never
price levels: split-adjusted levels embed future reverse splits (see data/alpaca.py).
"""
import numpy as np
import pandas as pd

from . import config as C


def dollar_volume_20(p):
    """20-day average dollar volume through t-1."""
    return (p.close.astype("float64") * p.vol).rolling(20).mean().shift(1)


def tradable(p):
    """Layer 0. Applied identically to the strategy and to every control. An earlier comparison let
    the hindsight universe skip this filter and overstated its advantage by roughly $177k."""
    return dollar_volume_20(p) >= C.LIQ_FLOOR


def meme_events(close, run=C.MEME_RUN, window=C.MEME_WINDOW):
    """Past runs of +run within `window` sessions, one per run (no overlap).

    An event is only KNOWABLE after its peak, so it becomes usable at peak + 1, never at the day the
    run began. Returns a list of dicts with integer positions."""
    c = np.asarray(close, dtype="float64")
    n, t, out = len(c), 0, []
    while t < n - 1:
        if np.isnan(c[t]):
            t += 1
            continue
        w = c[t + 1:min(t + 1 + window, n)]
        w = w[~np.isnan(w)]
        if len(w) == 0:
            t += 1
            continue
        if w.max() / c[t] - 1 >= run:
            seg = c[t + 1:min(t + 1 + window, n)]
            pk = t + 1 + int(np.nanargmax(seg))
            out.append({"ignition": t, "peak": pk, "gain": float(np.nanmax(seg) / c[t] - 1),
                        "knowable_from": pk + 1})
            t = pk + 1
        else:
            t += 1
    return out


def prior_meme_flag(p):
    """True from the day after the peak of a ticker's first meme event onwards."""
    flag = pd.DataFrame(False, index=p.close.index, columns=p.close.columns)
    for j, s in enumerate(p.close.columns):
        ev = meme_events(p.close[s].values)
        if ev and ev[0]["knowable_from"] < len(flag):
            flag.iloc[ev[0]["knowable_from"]:, j] = True
    return flag


def pit_universe(p):
    """v2 layer 1: (>=50% below the all-time high AND back above the 50-day average)
    OR (has had a meme event before), AND tradable. All-time high uses history from 2016."""
    cl_prev = p.close.shift(1)
    ath = cl_prev.cummax()
    fallen = (cl_prev / ath - 1) <= C.DD_FROM_ATH
    stabilised = cl_prev > p.close.rolling(50).mean().shift(1)
    return ((fallen & stabilised) | prior_meme_flag(p)) & tradable(p)
