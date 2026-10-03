"""FINRA bi-monthly short-interest files from 2021, one row per symbol per settlement.

    python scripts/fetch_finra.py

No key needed. The output also serves as a point-in-time listing record (see docs/spec, Module 22).
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from memescan import config as C  # noqa: E402
from memescan.data import finra  # noqa: E402


def main():
    C.CACHE.mkdir(parents=True, exist_ok=True)
    out = C.CACHE / "finra_all.parquet"
    have = pd.read_parquet(out) if out.exists() else pd.DataFrame(columns=["settle"])
    seen = set(pd.to_datetime(have["settle"]).dt.date) if len(have) else set()
    parts = [have] if len(have) else []
    for d in finra.candidate_settlement_dates():
        if any(abs((d - s).days) <= 2 for s in seen):
            continue
        df = finra.fetch_file(d)
        if df is not None:
            parts.append(df)
            seen.add(df["settle"].iloc[0].date())
            print(f"{df['settle'].iloc[0].date()}: {len(df):,} rows", flush=True)
            pd.concat(parts, ignore_index=True).to_parquet(out, index=False)


if __name__ == "__main__":
    main()
