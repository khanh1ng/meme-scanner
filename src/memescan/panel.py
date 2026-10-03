"""Daily price panel: long bars -> wide date x ticker frames."""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config as C


@dataclass
class Panel:
    open: pd.DataFrame
    high: pd.DataFrame
    low: pd.DataFrame
    close: pd.DataFrame
    vol: pd.DataFrame

    @property
    def dates(self):
        return list(self.close.index)

    @property
    def tickers(self):
        return list(self.close.columns)

    def truncate(self, last_day):
        """The panel as it would have existed at the end of last_day (for look-ahead tests)."""
        sl = slice(None, last_day)
        return Panel(self.open.loc[sl], self.high.loc[sl], self.low.loc[sl], self.close.loc[sl], self.vol.loc[sl])


def from_long(bars, min_adv=C.LIQ_FLOOR):
    """bars: columns ticker, date, open, high, low, close, vol (split-adjusted).

    Tickers whose 20-day dollar volume never reaches min_adv are dropped. This only saves memory:
    the per-day tradability filter applied later gives the same result."""
    b = bars.copy()
    b["date"] = pd.to_datetime(b["date"])
    b["dv"] = b["close"].astype("float64") * b["vol"]
    adv_max = b.groupby("ticker")["dv"].apply(lambda s: s.rolling(20).mean().max())
    b = b[b["ticker"].isin(set(adv_max[adv_max >= min_adv].index))]

    def wide(col, dtype):
        return b.pivot_table(index="date", columns="ticker", values=col).astype(dtype)
    return Panel(wide("open", "float32"), wide("high", "float32"), wide("low", "float32"),
                 wide("close", "float32"), wide("vol", "float64"))


def load(path, min_adv=C.LIQ_FLOOR):
    return from_long(pd.read_parquet(path), min_adv)


def atr(h, l, c, w=C.ATR_WIN):
    """Simple-average true range over w bars, per ticker array."""
    n = len(c)
    tr = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    out = np.full(n, np.nan)
    for i in range(w, n):
        out[i] = tr[i - w + 1:i + 1].mean()
    return out
