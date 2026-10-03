"""Daily SIP bars from 2016 for every US common stock in the symbol master. Resumable by chunk.

    APCA_API_KEY_ID=... APCA_API_SECRET_KEY=... python scripts/fetch_universe.py

History starts in 2016 so that "distance from the all-time high" is meaningful by 2021.
LIMITATION: the symbol master holds active listings only (survivorship). The point-in-time
membership fix (FINRA snapshots + Alpaca bars for delisted names) is specified in docs/spec, Module 22.
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from memescan import config as C  # noqa: E402
from memescan.data import alpaca  # noqa: E402

BATCH = 100


def main(adjustment="split"):
    C.CACHE.mkdir(parents=True, exist_ok=True)
    out = C.CACHE / ("universe_v2_daily.parquet" if adjustment == "split" else f"universe_{adjustment}_daily.parquet")
    done_f = out.with_suffix(".done.json")
    syms = alpaca.symbol_master()
    print(f"{len(syms)} symbols")
    done = set(json.loads(done_f.read_text())) if done_f.exists() else set()
    parts = [pd.read_parquet(out)] if out.exists() else []
    chunks = [syms[i:i + BATCH] for i in range(0, len(syms), BATCH)]
    for k, ch in enumerate(chunks):
        if ch[0] in done:
            continue
        df = alpaca.daily_bars(ch, adjustment=adjustment)
        if len(df):
            parts.append(df)
        done.add(ch[0])
        if (k + 1) % 10 == 0 or k == len(chunks) - 1:
            pd.concat(parts, ignore_index=True).to_parquet(out, index=False)
            done_f.write_text(json.dumps(sorted(done)))
            print(f"chunk {k + 1}/{len(chunks)}: {sum(len(p) for p in parts):,} bars", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "split")
