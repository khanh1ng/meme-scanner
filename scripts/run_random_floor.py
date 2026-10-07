"""Random-names floor as a distribution (docs/spec/random_floor_test.md). Writes
results/random_floor.csv (one row per draw) and results/random_floor.json (tests).

    MEMESCAN_CACHE=/path/to/cache python scripts/run_random_floor.py"""
import json
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from memescan import config as C, panel, universe, trigger, backtest, controls  # noqa: E402

N_DRAWS = 200
G = {}


def _draw(seed):
    U = controls.random_floor(G["trd"], G["n"], seed=seed)
    tk, eq = backtest.run(G["p"], trigger.signals(G["trig"], U, G["rv"]), G["dv20"], use_cost=True, legacy=False)
    s = backtest.stats(tk, eq, G["p"].dates)
    return dict(seed=seed, n=s["n"], exp=s["exp"], final=s["final"], sharpe=s["sharpe"])


def main():
    p = panel.load(C.CACHE / "universe_v2_daily.parquet")
    pit = universe.pit_universe(p)
    G.update(p=p, trd=universe.tradable(p), dv20=universe.dollar_volume_20(p), trig=trigger.ignition(p),
             rv=trigger.relative_volume(p), n=max(10, int(pit.sum(axis=1).mean())))
    with mp.get_context("fork").Pool(6) as pool:
        rows = pool.map(_draw, range(1, N_DRAWS + 1), chunksize=1)
    df = pd.DataFrame(rows).sort_values("seed")
    df.to_csv(C.RESULTS / "random_floor.csv", index=False)
    summ = pd.read_csv(C.RESULTS / "backtest_summary.csv")
    ref = summ[summ.engine == "corrected"].set_index("universe")
    out = {"draws": N_DRAWS, "names_per_day": G["n"],
           "random_exp": dict(mean=float(df.exp.mean()), p05=float(df.exp.quantile(.05)), p50=float(df.exp.median()),
                              p95=float(df.exp.quantile(.95)), min=float(df.exp.min()), max=float(df.exp.max()))}
    for key, name in (("pit", "PIT universe"), ("hindsight", "Hindsight 82, same filter (ceiling)")):
        v = float(ref.loc[name, "exp"])
        out[key] = dict(exp=v, p_value=float((1 + (df.exp >= v).sum()) / (N_DRAWS + 1)),
                        percentile=float((df.exp < v).mean()))
    (C.RESULTS / "random_floor.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
