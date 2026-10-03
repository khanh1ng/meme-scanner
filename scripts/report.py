"""Write the backtest tables from results/ into README.md and docs/FINDINGS.md, between markers.
No number in those tables is typed by hand.

    python scripts/report.py
"""
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"


def money(x):
    return f"${x:,.0f}" if x >= 0 else f"−${-x:,.0f}"


def table(df):
    head = "| Engine | Universe | Trades | Win rate | Mean net return / trade | Mean cost / trade | Final equity | CAGR | Sharpe | Max DD | P&L without top 10 |"
    sep = "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    rows = [f"| {r.engine} | {r.universe} | {r.n} | {r.win:.1%} | {r.exp:+.2%} | {r.cost:.2%} | {money(r.final)} | "
            f"{r.cagr:+.1%} | {r.sharpe:.2f} | {r.maxdd:.1%} | {money(r.pnl_ex_top10)} |" for r in df.itertuples()]
    return "\n".join([head, sep] + rows)


def headline(df, meta):
    c = df[df.engine == "corrected"].set_index("universe")
    l_ = df[df.engine == "legacy"].set_index("universe")
    pit, ceil, floor = "PIT universe", "Hindsight 82, same filter (ceiling)", "Random names, same filter (floor)"
    return (f"On {meta['sessions']:,} sessions ({meta['first']} to {meta['last']}) and {meta['tickers']:,} tickers, "
            f"with costs and next-open fills, the point-in-time strategy turns $100,000 into "
            f"{money(c.loc[pit, 'final'])} (Sharpe {c.loc[pit, 'sharpe']:.2f}); a universe of random names drawn "
            f"from the same tradable pool ends at {money(c.loc[floor, 'final'])} (Sharpe {c.loc[floor, 'sharpe']:.2f}). "
            f"Only the deliberately biased hindsight list makes money ({money(c.loc[ceil, 'final'])}, Sharpe "
            f"{c.loc[ceil, 'sharpe']:.2f}). The research notebook's own engine reported Sharpe "
            f"{l_.loc[pit, 'sharpe']:.2f} for the same universe; the two defects fixed in "
            f"`src/memescan/backtest.py` move it to {c.loc[pit, 'sharpe']:.2f}.")


def fill(path, key, text):
    s = path.read_text()
    pat = re.compile(rf"(<!-- {key}:START -->\n).*?(<!-- {key}:END -->)", re.S)
    assert pat.search(s), f"marker {key} missing in {path}"
    path.write_text(pat.sub(lambda m: m.group(1) + text + "\n" + m.group(2), s))


def main():
    df = pd.read_csv(R / "backtest_summary.csv")
    meta = json.loads((R / "backtest_meta.json").read_text())
    for p in (ROOT / "README.md", ROOT / "docs" / "FINDINGS.md"):
        fill(p, "HEADLINE", headline(df, meta))
        fill(p, "TABLE", table(df))
    print("README.md and docs/FINDINGS.md updated")


if __name__ == "__main__":
    main()
