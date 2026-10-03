# ARCHIVE — superseded by scripts/ and src/memescan/. Credentials removed.
#!/usr/bin/env python3
"""Universe lon: TAT CA US common stocks (active) tren NYSE/NASDAQ/AMEX/ARCA/BATS,
daily bars SIP tu 2016 (de ATH co y nghia truoc thoi meme 2021).
Batch endpoint + 10k calls/min -> nhanh. RESUMABLE theo chunk.
LUU Y: key AK la live account - script CHI GET data, khong bao gio dat lenh."""
import os
import requests, pandas as pd, numpy as np, json, time
from pathlib import Path

C = Path("meme_cache"); C.mkdir(exist_ok=True)
OUT, DONE = C/"universe_v2_daily.parquet", C/"universe_v2_done.json"
H = {"APCA-API-KEY-ID": os.environ["APCA_API_KEY_ID"],
     "APCA-API-SECRET-KEY": os.environ["APCA_API_SECRET_KEY"]}
START = "2016-01-01"; BATCH = 100

def get_symbols():
    r = requests.get("https://api.alpaca.markets/v2/assets",
                     params={"status": "active", "asset_class": "us_equity"}, headers=H, timeout=60)
    r.raise_for_status()
    syms = sorted({a["symbol"] for a in r.json()
                   if a.get("tradable")
                   and a.get("exchange") in ("NYSE", "NASDAQ", "AMEX", "ARCA", "BATS")
                   and a["symbol"].isalpha() and 1 <= len(a["symbol"]) <= 5})
    return syms

def fetch_batch(symbols):
    rows, tok = [], None
    while True:
        p = {"symbols": ",".join(symbols), "timeframe": "1Day", "start": START,
             "limit": 10000, "feed": "sip", "adjustment": "split"}
        if tok: p["page_token"] = tok
        for att in range(5):
            try:
                r = requests.get("https://data.alpaca.markets/v2/stocks/bars", params=p, headers=H, timeout=90)
                if r.status_code == 429: time.sleep(3); continue
                r.raise_for_status(); break
            except Exception: time.sleep(5)
        else: return rows
        j = r.json()
        for s, bl in (j.get("bars") or {}).items():
            for b in bl:
                rows.append((s, b["t"][:10], b["o"], b["h"], b["l"], b["c"], b["v"]))
        tok = j.get("next_page_token")
        if not tok: return rows

def main():
    syms = get_symbols()
    print(f"{len(syms)} symbols du dieu kien", flush=True)
    done = set(json.loads(DONE.read_text())) if DONE.exists() else set()
    chunks = [syms[i:i+BATCH] for i in range(0, len(syms), BATCH)]
    parts = [pd.read_parquet(OUT)] if OUT.exists() else []
    for k, ch in enumerate(chunks):
        key = ch[0]
        if key in done: continue
        rows = fetch_batch(ch)
        if rows:
            df = pd.DataFrame(rows, columns=["ticker", "date", "open", "high", "low", "close", "vol"])
            for c in ("open", "high", "low", "close"): df[c] = df[c].astype("float32")
            df["vol"] = df["vol"].astype("float64")
            parts.append(df)
        done.add(key)
        if (k+1) % 10 == 0 or k == len(chunks)-1:
            pd.concat(parts, ignore_index=True).to_parquet(OUT, index=False)
            DONE.write_text(json.dumps(sorted(done)))
            n = sum(len(p) for p in parts)
            print(f"  chunk {k+1}/{len(chunks)} | {n:,} bars", flush=True)
    print("HOAN TAT", flush=True)

if __name__ == "__main__":
    main()
