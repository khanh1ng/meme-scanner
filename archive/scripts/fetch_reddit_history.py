# ARCHIVE — superseded by scripts/ and src/memescan/. Credentials removed.
#!/usr/bin/env python3
"""Fetch lich su Reddit (Arctic Shift) -> dem ticker mention theo NGAY.
RESUMABLE: checkpoint tung ngay. Chay lai la tu bo qua ngay da xong.
Dung: caffeinate -is python3 fetch_reddit_history.py
"""
import requests, pandas as pd, numpy as np, time, re, sys, json
from pathlib import Path
from datetime import date, timedelta

C = Path("meme_cache"); C.mkdir(exist_ok=True)
OUT  = C / "reddit_mentions.parquet"
DONE = C / "reddit_days_done.json"
API  = "https://arctic-shift.photon-reddit.com/api/posts/search"
UA   = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/124.0.0.0 Safari/537.36"}

SUBS       = ["wallstreetbets"]   # chi WSB -> vua 1 dem (~7.6h). Them sub = them thoi gian.
START, END = date(2021, 1, 1), date(2026, 6, 30)
MAX_PAGES  = 4          # 4 x 100 = toi da 400 post/sub/ngay (mau nhat quan -> ty le van dung)
SLEEP_OK   = 2.0        # nhip binh thuong
SLEEP_BAD  = 20.0       # khi bi 422/429

TICKERS = set(pd.read_parquet(C / "pool_universe.parquet").ticker.unique())
CASH = re.compile(r"\$([A-Z]{1,5})\b")
WORD = re.compile(r"\b([A-Z]{2,5})\b")
STOP = {"THE","AND","FOR","YOU","ARE","NOT","BUT","ALL","CAN","HAS","WAS","WILL","GET",
        "NOW","NEW","OUT","ONE","TWO","DD","CEO","IPO","USA","ATH","YOLO","FOMO","WSB",
        "SEC","FED","EPS","ETF","LOL","IMO","TLDR","EOD","OTM","ITM","PM","AH","IV","US"}
VALID = TICKERS - STOP

def fetch_day(sub, d):
    """Tra ve list text cua 1 ngay. Retry co backoff."""
    texts, after = [], None
    a = f"{d}T00:00:00Z"; b = f"{d + timedelta(days=1)}T00:00:00Z"
    for page in range(MAX_PAGES):
        par = {"subreddit": sub, "after": a, "before": b, "limit": 100,
               "fields": "title,selftext,created_utc", "sort": "asc"}
        if after: par["after"] = after
        for attempt in range(6):
            try:
                r = requests.get(API, params=par, headers=UA, timeout=45)
                if r.status_code == 200:
                    data = r.json().get("data") or []
                    if not data: return texts
                    for p in data:
                        texts.append(f"{p.get('title','')} {p.get('selftext','')}")
                    last = data[-1].get("created_utc")
                    after = pd.to_datetime(last, unit="s").strftime("%Y-%m-%dT%H:%M:%SZ") if last else None
                    time.sleep(SLEEP_OK)
                    break
                if r.status_code in (422, 429, 503):
                    time.sleep(SLEEP_BAD * (attempt + 1)); continue
                return texts
            except Exception:
                time.sleep(SLEEP_BAD * (attempt + 1))
        else:
            return texts
        if not after: break
    return texts

def count_mentions(texts):
    cnt = {}
    for t in texts:
        up = t.upper()
        found = set(CASH.findall(up)) | (set(WORD.findall(up)) & VALID)
        for tk in found:
            if tk in VALID: cnt[tk] = cnt.get(tk, 0) + 1
    return cnt

def main():
    done = set(json.loads(DONE.read_text())) if DONE.exists() else set()
    rows = [] if not OUT.exists() else [pd.read_parquet(OUT)]
    d, n_new = START, 0
    total_days = (END - START).days + 1
    print(f"Bat dau. Da xong {len(done)}/{total_days} ngay.", flush=True)
    while d <= END:
        key = d.isoformat()
        if key in done: d += timedelta(days=1); continue
        allc = {}
        for sub in SUBS:
            for tk, c in count_mentions(fetch_day(sub, d)).items():
                allc[tk] = allc.get(tk, 0) + c
        if allc:
            rows.append(pd.DataFrame([{"date": pd.Timestamp(d), "ticker": k, "mentions": v}
                                      for k, v in allc.items()]))
        done.add(key); n_new += 1
        if n_new % 5 == 0:                                   # checkpoint moi 5 ngay
            pd.concat(rows, ignore_index=True).to_parquet(OUT, index=False)
            DONE.write_text(json.dumps(sorted(done)))
            print(f"  [{key}] xong {len(done)}/{total_days} ngay "
                  f"({len(done)/total_days:.1%}) | {len(allc)} ma hom nay", flush=True)
        d += timedelta(days=1)
    pd.concat(rows, ignore_index=True).to_parquet(OUT, index=False)
    DONE.write_text(json.dumps(sorted(done)))
    print("HOAN TAT ->", OUT, flush=True)

if __name__ == "__main__":
    main()
