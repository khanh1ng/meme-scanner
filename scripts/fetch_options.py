"""Daily out-of-the-money call volume per underlying from Alpaca OPRA (history from 2024-01-22).

    APCA_API_KEY_ID=... APCA_API_SECRET_KEY=... python scripts/fetch_options.py

A call is OTM when its strike exceeds the underlying's close on the same day. Both date indexes are
normalised to calendar dates first: a 05:00 vs 00:00 stamp mismatch once produced an empty file.
"""
import json
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from memescan import config as C  # noqa: E402
from memescan.data import alpaca  # noqa: E402
from memescan.gates import calendar_index  # noqa: E402

START = "2024-01-22"


def main(tickers=None):
    out, done_f = C.CACHE / "options_flow.parquet", C.CACHE / "options_tickers_done.json"
    bars = pd.read_parquet(C.CACHE / "universe_v2_daily.parquet", columns=["ticker", "date", "close"])
    close = bars.pivot_table(index="date", columns="ticker", values="close")
    close.index = calendar_index(close.index)
    tickers = tickers or [t for t in close.columns if close[t].loc[START:].notna().sum() > 200]
    done = set(json.loads(done_f.read_text())) if done_f.exists() else set()
    acc = [pd.read_parquet(out)] if out.exists() else []
    for k, sym in enumerate(tickers):
        if sym in done:
            continue
        meta = {c["symbol"]: float(c["strike_price"]) for c in alpaca.call_contracts(sym, START)}
        frames = []
        occ = list(meta)
        for i in range(0, len(occ), 100):
            frames.append(alpaca.option_daily_volume(occ[i:i + 100], START))
            time.sleep(0.4)
        d = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if len(d):
            d["date"] = calendar_index(d["date"])
            d["strike"] = d["contract"].map(meta)
            und = close[sym].reindex(d["date"]).values
            d = d[(d["strike"].values > und) & pd.notna(und)]
            g = d.groupby("date")["vol"].sum().rename("otm_call_vol").reset_index()
            g["ticker"] = sym
            acc.append(g)
        done.add(sym)
        if (k + 1) % 5 == 0 and acc:
            pd.concat(acc, ignore_index=True).to_parquet(out, index=False)
            done_f.write_text(json.dumps(sorted(done)))
            print(f"{sym}: {len(done)}/{len(tickers)}", flush=True)
    if acc:
        pd.concat(acc, ignore_index=True).to_parquet(out, index=False)
    done_f.write_text(json.dumps(sorted(done)))


if __name__ == "__main__":
    main(sys.argv[1:] or None)
