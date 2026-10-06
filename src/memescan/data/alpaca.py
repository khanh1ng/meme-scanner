"""Alpaca market data: symbol master, daily bars, options contracts and bars.

Two price panels are needed. Split-adjusted bars are used for returns. Raw bars must be used for any
price LEVEL filter, because Alpaca adjusts backwards: a 1-for-100 reverse split in 2023 multiplies the
displayed 2021 price by 100, so filtering on an adjusted level reads a future corporate action.

This module only issues GET requests. It never places orders.
"""
import time

import pandas as pd
import requests

from .. import config as C


def _get(url, params, headers, timeout=90, tries=5):
    for attempt in range(tries):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            if r.status_code == 429:
                time.sleep(3 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            time.sleep(5 * (attempt + 1))
    return None


def symbol_master(status="active"):
    """US common stocks on the main exchanges. With status='active' this is a SURVIVOR list:
    delisted names are missing, which biases a long-only backtest upwards."""
    j = _get(C.EP_ASSETS, {"status": status, "asset_class": "us_equity"}, C.alpaca_headers(), timeout=60)
    return sorted({a["symbol"] for a in (j or [])
                   if a.get("tradable") and a.get("exchange") in C.EXCHANGES
                   and a["symbol"].isalpha() and 1 <= len(a["symbol"]) <= 5})


def daily_bars(symbols, start="2016-01-01", adjustment="split", feed="sip"):
    """Daily bars for up to 100 symbols per request, all pages. Dates are taken in New York time."""
    rows, token = [], None
    while True:
        p = {"symbols": ",".join(symbols), "timeframe": "1Day", "start": start, "limit": 10000,
             "feed": feed, "adjustment": adjustment}
        if token:
            p["page_token"] = token
        j = _get(C.EP_BARS, p, C.alpaca_headers())
        if j is None:
            break
        for s, bl in (j.get("bars") or {}).items():
            for b in bl:
                ts = pd.Timestamp(b["t"]).tz_convert("America/New_York")
                rows.append((s, ts.date().isoformat(), b["o"], b["h"], b["l"], b["c"], b["v"]))
        token = j.get("next_page_token")
        if not token:
            break
    df = pd.DataFrame(rows, columns=["ticker", "date", "open", "high", "low", "close", "vol"])
    for c in ("open", "high", "low", "close"):
        df[c] = df[c].astype("float32")
    df["vol"] = df["vol"].astype("float64")
    return df


def call_contracts(underlying, expiry_from):
    """All call contracts (including expired) with expiry on or after expiry_from."""
    out, token = [], None
    for _ in range(40):
        p = {"underlying_symbols": underlying, "limit": 10000, "expiration_date_gte": expiry_from}
        if token:
            p["page_token"] = token
        j = _get(C.EP_OPT_CONTRACTS, p, C.alpaca_headers(), timeout=60)
        if j is None:
            break
        out += [c for c in j.get("option_contracts", []) if c.get("type") == "call"]
        token = j.get("next_page_token")
        if not token:
            break
    return out


def option_daily_volume(occ_symbols, start):
    """Daily volume per option contract. OPRA history at this price point starts 2024-01-22."""
    rows, token = [], None
    for _ in range(60):
        p = {"symbols": ",".join(occ_symbols), "timeframe": "1Day", "start": start, "limit": 10000}
        if token:
            p["page_token"] = token
        j = _get(C.EP_OPT_BARS, p, C.alpaca_headers(), timeout=60)
        if j is None:
            break
        for s, bl in (j.get("bars") or {}).items():
            for b in bl:
                rows.append({"contract": s, "date": b["t"][:10], "vol": b.get("v", 0)})
        token = j.get("next_page_token")
        if not token:
            break
    return pd.DataFrame(rows)
