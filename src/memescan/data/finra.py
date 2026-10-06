"""FINRA bi-monthly short interest.

Each file is a point-in-time snapshot of every security that existed on its settlement date, so the
file set doubles as a free, dated listing record from 2021 (used to fight survivorship bias).
A row is usable only from settle + SI_LAG_DAYS: that is the publication lag.
"""
import io
from datetime import date, timedelta

import pandas as pd
import requests

from .. import config as C


def candidate_settlement_dates(start=date(2021, 1, 1), end=None):
    """Settlements fall near the 15th and the last business day of each month."""
    end = end or date.today()
    d = date(start.year, start.month, 1)
    while d <= end:
        mid = date(d.year, d.month, 15)
        nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
        yield mid
        yield nxt - timedelta(days=1)
        d = nxt


def fetch_file(settle):
    """Probe settle-2..settle+2 (holidays move the date). Returns a DataFrame or None."""
    for off in (0, -1, 1, -2, 2):
        d = settle + timedelta(days=off)
        url = C.EP_FINRA.format(yyyymmdd=d.strftime("%Y%m%d"))
        r = requests.get(url, headers=C.BROWSER_UA, timeout=60)
        if r.status_code == 200 and len(r.content) > 50_000:
            t = pd.read_csv(io.StringIO(r.text), sep="|")
            return pd.DataFrame({
                "ticker": t["symbolCode"],
                "short_int": t["currentShortPositionQuantity"],
                "prev_si": t["previousShortPositionQuantity"],
                "adv": t["averageDailyVolumeQuantity"],
                "dtc": t["daysToCoverQuantity"],
                "settle": pd.Timestamp(d),
            })
    return None


def usable(si):
    """Attach the date from which each row may be used."""
    si = si.copy()
    si["usable_from"] = pd.to_datetime(si["settle"]) + pd.Timedelta(days=C.SI_LAG_DAYS)
    return si


def asof(si, ticker, day):
    """Latest short-interest row for ticker that was public on `day`, or None."""
    g = si[(si["ticker"] == ticker) & (si["usable_from"] <= pd.Timestamp(day))]
    return None if g.empty else g.sort_values("settle").iloc[-1]
