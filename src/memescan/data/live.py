"""Live-only sources. None of these has history, so none can be backtested.

They are used by the forward recorder: a daily snapshot builds the point-in-time history that a
later, rigorous backtest needs. Every function returns None on failure; callers must treat None as
missing, never as zero (see gates.null_policy).
"""
import pandas as pd
import requests

from .. import config as C


def apewisdom(pages=(1, 2, 3, 4, 5), flt="wallstreetbets"):
    """Mentions, mentions 24h ago and RANK. A rank change says attention is arriving; a high level
    says the name is already crowded (measured IC of mention level was negative)."""
    rows = []
    for page in pages:
        try:
            r = requests.get(C.EP_APEWISDOM.format(flt=flt, page=page), headers=C.BROWSER_UA, timeout=10)
        except requests.RequestException:
            break
        if r.status_code != 200:
            break
        for it in r.json().get("results", []):
            rows.append({"ticker": (it.get("ticker") or "").upper(),
                         "mentions": float(it.get("mentions") or 0),
                         "mentions_24h": float(it.get("mentions_24h_ago") or 0),
                         "rank": float(it.get("rank") or 9999),
                         "rank_24h": float(it.get("rank_24h_ago") or 9999)})
    if not rows:
        return None
    df = pd.DataFrame(rows).drop_duplicates("ticker")
    df["rank_delta"] = df["rank_24h"] - df["rank"]   # positive = climbing
    return df


def stocktwits_sentiment(sym):
    """StockTwits labels each message Bullish or Bearish, so stance needs no model call.
    The endpoint returns 403/429 intermittently: best effort only."""
    try:
        r = requests.get(C.EP_STOCKTWITS.format(sym=sym), headers=C.BROWSER_UA, timeout=8)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    labels = [((m.get("entities") or {}).get("sentiment") or {}).get("basic") for m in r.json().get("messages", [])]
    bull, bear = labels.count("Bullish"), labels.count("Bearish")
    return {"ticker": sym, "n_msg": len(labels), "bull_ratio": bull / max(bull + bear, 1)}


def iborrowdesk(sym):
    """Borrow fee and shares available. A snapshot, not history: record it daily from now on."""
    try:
        r = requests.get(C.EP_IBORROW.format(sym=sym), headers=C.BROWSER_UA, timeout=10)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    j = r.json()
    fee, avail = j.get("latest_fee"), j.get("latest_available")
    if fee is None or avail is None:              # fall back to the newest entry of a series
        series = j.get("real_time") or j.get("daily") or []
        if series:
            fee = series[-1].get("fee", fee)
            avail = series[-1].get("available", avail)
    return {"ticker": sym, "fee_pct": fee, "available": avail,
            "recorded_at": pd.Timestamp.now(tz="UTC")}
