"""Layer 2: the ignition trigger, evaluated at the close of day t. Entry is at the open of t+1."""
from collections import defaultdict

import numpy as np

from . import config as C


def relative_volume(p):
    return p.vol / p.vol.rolling(20).mean().shift(1)


def ignition(p):
    """Unusual volume, closing in the upper part of the range, up on the day, above MA20,
    5-day momentum, and not already more than EXT_CAP above MA20 (exhaustion cap)."""
    ma20 = p.close.rolling(20).mean().shift(1)
    rv = relative_volume(p)
    typical = (p.high + p.low + p.close) / 3
    mom5 = p.close / p.close.shift(5) - 1
    ext = p.close / ma20 - 1
    return ((rv >= C.RVOL_MIN) & (p.close > typical) & (p.close > p.close.shift(1))
            & (p.close > ma20) & (ext <= C.EXT_CAP) & (mom5 > C.MOM5_MIN))


def signals(trigger_mask, universe_mask, rvol):
    """{date: [(rvol, ticker), ...]} for names in the universe whose trigger fired."""
    both = trigger_mask & universe_mask
    st = both.stack()
    out = defaultdict(list)
    for d, s in st[st].index:
        r = float(rvol.at[d, s])
        out[d].append((r if not np.isnan(r) else 0.0, s))
    return out
