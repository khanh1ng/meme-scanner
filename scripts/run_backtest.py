"""Rebuild the v2 comparison from the cached panel and write results/.

    MEMESCAN_CACHE=/path/to/cache python scripts/run_backtest.py

Needs universe_v2_daily.parquet in the cache (scripts/fetch_universe.py builds it).
Runs every universe twice: legacy=True reproduces the research notebook, legacy=False is the
corrected engine (see src/memescan/backtest.py)."""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from memescan import config as C, panel, universe, trigger, backtest, controls  # noqa: E402

HINDSIGHT = [t for line in (Path(__file__).resolve().parents[1] / "src/memescan/hindsight_82.txt").read_text().splitlines()
             if not line.startswith("#") for t in line.split()]


def main():
    p = panel.load(C.CACHE / "universe_v2_daily.parquet")
    dates = p.dates
    print(f"panel: {len(dates)} sessions x {len(p.tickers)} tickers, {dates[0].date()} to {dates[-1].date()}")
    trd = universe.tradable(p)
    dv20 = universe.dollar_volume_20(p)
    pit = universe.pit_universe(p)
    trig = trigger.ignition(p)
    rv = trigger.relative_volume(p)
    n_per_day = max(10, int(pit.sum(axis=1).mean()))
    unis = {"PIT universe": pit,
            "Hindsight 82, same filter (ceiling)": controls.hindsight_ceiling(trd, HINDSIGHT),
            "Random names, same filter (floor)": controls.random_floor(trd, n_per_day)}
    C.RESULTS.mkdir(exist_ok=True)
    rows = []
    for legacy in (True, False):
        for name, U in unis.items():
            tk, eq = backtest.run(p, trigger.signals(trig, U, rv), dv20, use_cost=True, legacy=legacy)
            rows.append({"engine": "legacy" if legacy else "corrected", "universe": name,
                         **backtest.stats(tk, eq, dates)})
            if not legacy:
                tag = name.split()[0].lower()
                tk.to_csv(C.RESULTS / f"trades_{tag}.csv", index=False)
                eq.rename("equity").to_csv(C.RESULTS / f"equity_{tag}.csv")
        tk, eq = backtest.run(p, trigger.signals(trig, pit, rv), dv20, use_cost=False, legacy=legacy)
        rows.append({"engine": "legacy" if legacy else "corrected", "universe": "PIT universe, no costs",
                     **backtest.stats(tk, eq, dates)})
    out = pd.DataFrame(rows)
    out.to_csv(C.RESULTS / "backtest_summary.csv", index=False)
    meta = {"sessions": len(dates), "tickers": len(p.tickers), "first": str(dates[0].date()),
            "last": str(dates[-1].date()), "random_names_per_day": n_per_day,
            "pit_names_per_day": float(pit.sum(axis=1).mean())}
    (C.RESULTS / "backtest_meta.json").write_text(json.dumps(meta, indent=1))
    pd.set_option("display.width", 200)
    print(out[["engine", "universe", "n", "win", "exp", "cost", "final", "cagr", "sharpe", "maxdd",
               "pnl_ex_top10", "curve_end_minus_final"]].to_string(index=False))


if __name__ == "__main__":
    main()
