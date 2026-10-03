"""Daily ticker mentions on r/wallstreetbets from the Arctic Shift archive. Resumable by day.

    python scripts/fetch_reddit.py 2021-01-01 2026-06-30

A full pass takes one night. Valid tickers come from the cached price panel; English words are
removed afterwards with the burst blocklist (memescan.data.reddit.burst_blocklist).
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from memescan import config as C  # noqa: E402
from memescan.data import reddit  # noqa: E402


def main(start, end):
    out, done_f = C.CACHE / "reddit_mentions.parquet", C.CACHE / "reddit_days_done.json"
    valid = set(pd.read_parquet(C.CACHE / "universe_v2_daily.parquet", columns=["ticker"]).ticker.unique())
    done = set(json.loads(done_f.read_text())) if done_f.exists() else set()
    rows = [pd.read_parquet(out)] if out.exists() else []
    d = start
    while d <= end:
        if d.isoformat() not in done:
            counts = {}
            for text in reddit.fetch_day(d):
                for t in reddit.extract_tickers(text, valid):
                    counts[t] = counts.get(t, 0) + 1
            if counts:
                rows.append(pd.DataFrame({"date": pd.Timestamp(d), "ticker": list(counts),
                                          "mentions": list(counts.values())}))
            done.add(d.isoformat())
            if len(done) % 5 == 0:
                pd.concat(rows, ignore_index=True).to_parquet(out, index=False)
                done_f.write_text(json.dumps(sorted(done)))
                print(f"{d}: {len(done)} days done", flush=True)
        d += timedelta(days=1)
    if rows:
        pd.concat(rows, ignore_index=True).to_parquet(out, index=False)
    done_f.write_text(json.dumps(sorted(done)))


if __name__ == "__main__":
    a = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2021, 1, 1)
    b = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()
    main(a, b)
