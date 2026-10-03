# ARCHIVE — superseded by scripts/ and src/memescan/. Credentials removed.
#!/usr/bin/env python3
"""OTM call volume theo ngay tu Alpaca OPRA (co tu 2024-01-22).
RESUMABLE theo tung ticker. Dung: caffeinate -is python3 fetch_options_flow.py"""
import os
import requests, pandas as pd, numpy as np, time, json, sys
from pathlib import Path

C = Path("meme_cache")
OUT, DONE = C / "options_flow.parquet", C / "options_tickers_done.json"
H = {"APCA-API-KEY-ID": os.environ["APCA_API_KEY_ID"],
     "APCA-API-SECRET-KEY": os.environ["APCA_API_SECRET_KEY"]}
TRADE, DATA = "https://paper-api.alpaca.markets", "https://data.alpaca.markets"
START = "2024-01-22"          # OPRA free bat dau tu day

px = pd.read_parquet(C / "pool_universe.parquet")
# CHUAN HOA ve NUA DEM: pool co timestamp 05:00, bars options co 00:00.
# Neu khong normalize thi reindex ra toan NaN -> khong phan loai duoc OTM -> file rong.
px["date"] = pd.to_datetime(px["date"]).dt.tz_localize(None).dt.normalize()
CLOSE = px.pivot(index="date", columns="ticker", values="close")
SYMS = [t for t in CLOSE.columns if CLOSE[t].notna().sum() > 200]

def contracts(sym):
    """Tat ca hop dong CALL (ke ca da het han) co expiry >= START."""
    out, tok = [], None
    for _ in range(40):
        p = {"underlying_symbols": sym, "limit": 10000, "expiration_date_gte": START}
        if tok: p["page_token"] = tok
        try:
            r = requests.get(f"{TRADE}/v2/options/contracts", params=p, headers=H, timeout=60)
            if r.status_code != 200: break
            j = r.json()
            out += [c for c in j.get("option_contracts", []) if c.get("type") == "call"]
            tok = j.get("next_page_token")
            if not tok: break
        except Exception:
            time.sleep(5)
    return out

def bars(symbols):
    """Daily bars cho nhieu hop dong 1 luc."""
    rows, tok = [], None
    for _ in range(60):
        p = {"symbols": ",".join(symbols), "timeframe": "1Day", "start": START, "limit": 10000}
        if tok: p["page_token"] = tok
        try:
            r = requests.get(f"{DATA}/v1beta1/options/bars", params=p, headers=H, timeout=60)
            if r.status_code == 429: time.sleep(10); continue
            if r.status_code != 200: break
            j = r.json()
            for s, bl in (j.get("bars") or {}).items():
                for b in bl: rows.append({"sym": s, "date": b["t"][:10], "vol": b.get("v", 0)})
            tok = j.get("next_page_token")
            if not tok: break
        except Exception:
            time.sleep(5)
    return rows

def main():
    done = set(json.loads(DONE.read_text())) if DONE.exists() else set()
    acc = [pd.read_parquet(OUT)] if OUT.exists() else []
    print(f"Bat dau. Da xong {len(done)}/{len(SYMS)} ma.", flush=True)
    for k, sym in enumerate(SYMS):
        if sym in done: continue
        cs = contracts(sym)
        if not cs:
            done.add(sym); continue
        meta = {c["symbol"]: (float(c["strike_price"]), c["expiration_date"]) for c in cs}
        allrows = []
        syms = list(meta)
        for i in range(0, len(syms), 100):
            allrows += bars(syms[i:i+100]); time.sleep(.4)
        if allrows:
            d = pd.DataFrame(allrows)
            d["date"] = pd.to_datetime(d["date"])
            d["strike"] = d["sym"].map(lambda s: meta[s][0])
            und = CLOSE[sym].reindex(d["date"].dt.normalize()).values   # gia co so cung ngay
            d["otm"] = (d["strike"].values > und) & ~pd.isna(und)        # call OTM = strike > gia
            g = (d[d["otm"]].groupby("date")["vol"].sum().rename("otm_call_vol").reset_index())
            g["ticker"] = sym
            if len(g): acc.append(g[["date", "ticker", "otm_call_vol"]])
        done.add(sym)
        if (k + 1) % 5 == 0 or k == len(SYMS) - 1:
            if acc: pd.concat(acc, ignore_index=True).to_parquet(OUT, index=False)
            DONE.write_text(json.dumps(sorted(done)))
            print(f"  [{sym}] {len(done)}/{len(SYMS)} ma | {len(cs)} call contracts", flush=True)
    if acc:
        pd.concat(acc, ignore_index=True).to_parquet(OUT, index=False)
        print("HOAN TAT ->", OUT, flush=True)
    else:
        print("!!! CANH BAO: khong thu duoc dong nao - kiem tra lech timestamp", flush=True)
    DONE.write_text(json.dumps(sorted(done)))

if __name__ == "__main__":
    main()
