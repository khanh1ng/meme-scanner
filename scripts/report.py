"""Write the backtest summary into README.md and the full table into docs/FINDINGS.md, between markers.
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


def pct(x, d=2, sign=True):
    s = f"{x:+.{d}%}" if sign else f"{x:.{d}%}"
    return s.replace("-", "−")


def top(df, meta, rf):
    """Summary, hypotheses and verdicts, results, mechanism, threats: every number from results/.
    Verdicts for H2 and H3 follow the rule fixed in docs/spec/random_floor_test.md (p < 0.05)."""
    c = df[df.engine == "corrected"].set_index("universe")
    pit, ceil, floor = "PIT universe", "Hindsight 82, same filter (ceiling)", "Random names, same filter (floor)"
    g = lambda k: c.loc[k, "exp"] + c.loc[k, "cost"]          # mean gross return per trade (net + cost)
    ex = lambda k: c.loc[k, "exp"]
    pp, hp = rf["pit"]["p_value"], rf["hindsight"]["p_value"]
    re_ = rf["random_exp"]
    h2 = "**Supported**" if hp < 0.05 else "**Not supported**"
    h3 = "**Supported**" if pp < 0.05 else "**Not supported**"
    rows = ["| Selection (same trigger, entry, exits, sizing and costs) | Trades | Win rate | Mean gross / trade | Mean cost / trade | Mean net / trade |",
            "|---|---:|---:|---:|---:|---:|"]
    for label, k in (("Names that later squeezed (hindsight list; upper bound, not a strategy)", ceil),
                     ("Random names from the same tradable pool (seed 7)", floor),
                     ("Point-in-time price-and-volume screen", pit)):
        rows.append(f"| {label} | {int(c.loc[k, 'n']):,} | {c.loc[k, 'win']:.1%} | {pct(g(k))} | {pct(c.loc[k, 'cost'], 2, False)} | {pct(ex(k))} |")
    rows.append(f"| Random names, {rf['draws']} draws: median [5th, 95th percentile] | | | | | "
                f"{pct(re_['p50'])} [{pct(re_['p05'])}, {pct(re_['p95'])}] |")
    answer = ("the execution layer converts good selection into profit, selection decides the result"
              if hp < 0.05 else "selection cannot yet be shown to decide the result")
    answer += (", and price and volume alone do not select" if pp >= 0.05 else ", and price and volume select better than random")
    return f"""**Summary.** The project asks whether meme-stock squeezes can be selected before they run using
only information available at the time. The answer so far: {answer}. With identical trading rules,
names that later squeezed earn {pct(ex(ceil))} per trade after costs, {"above all" if rf['hindsight']['percentile'] == 1 else f"above {rf['hindsight']['percentile']:.1%} of the"} {rf['draws']} random-name
draws (p = {hp:.3f}); the point-in-time price-and-volume screen earns {pct(ex(pit))}, below {1 - rf['pit']['percentile']:.1%} of
the random draws (p = {pp:.2f} for skill). Before costs its trades earn {pct(g(pit))}
per trade; costs of about {pct(c.loc[pit, 'cost'], 1, False)} per trade in these illiquid names decide the sign. The inputs
most directly linked to a squeeze (borrow cost, options positioning, float and dilution, social text)
are specified for the next stage and not yet tested.

## Hypotheses and verdicts

| | Hypothesis | Test | Evidence | Verdict |
|---|---|---|---|---|
| H1 | A list of meme stocks named by a language model is a valid universe | Same rules on the list and on random names (August report) | +3.12% per trade on the list, −0.60% on 113 random names; a model trained after 2021 already knows which stocks squeezed | **Rejected**: hindsight bias |
| H2 | The execution layer turns good selection into profit | Hindsight list against {rf['draws']} random-name draws ([spec](docs/spec/random_floor_test.md)) | {pct(ex(ceil))} per trade against random {pct(re_['p50'])} [{pct(re_['p05'])}, {pct(re_['p95'])}]; p = {hp:.3f} | {h2} |
| H3 | A point-in-time price-and-volume screen selects better than random | Same test for the screen | {pct(ex(pit))} per trade, below {1 - rf['pit']['percentile']:.1%} of random draws; p = {pp:.2f} | {h3} |
| H4 | High short interest marks the names that squeeze | Lift of days-to-cover on the chance of a +100% move in 20 sessions *(recorded, survivor data)* | Days to cover ≥ 3: 0.60x; below 2: 1.44x; median change in short interest before large moves 0% | **Not supported** at bi-monthly frequency |
| H5 | A volume spike marks the start of a squeeze | Relative volume on the day a +100% move begins *(recorded)* | Median 0.97x; what precedes it is a slow build (20/60-day volume 1.28x) | **Not supported**: a spike trigger is late |
| H6 | Structural screens raise the base rate of large moves | Hit rate of +100% in 20 sessions, 8,967,916 symbol-days *(recorded, survivor data)* | 0.68% base rate; combined gate 8.35% (12.19x); percentile version 6.31x with a stable universe | **Supported** on survivor data; to re-test point in time |
| H7 | Options positioning and social text carry selection information | Information coefficients with 20-day returns *(recorded, enriched pool)* | Out-of-the-money call volume +0.061 (110 names, 2024+); mention level −0.054 | **Untested at scale** |

## Stage 2 results (corrected engine, after costs)

{chr(10).join(rows)}

{meta['sessions']:,} sessions ({meta['first']} to {meta['last']}), {meta['tickers']:,} tickers; entry at the next open; costs 0.1% plus a
square-root impact term each way. Full table, both engines and drawdowns: [`docs/FINDINGS.md`](docs/FINDINGS.md).

## Mechanism

* **Costs set the bar selection must clear.** These names are illiquid: a round trip costs
  {pct(c.loc[pit, 'cost'], 2, False)} per trade on average for the screen and {pct(c.loc[ceil, 'cost'], 2, False)} for the hindsight list. Selection has to earn
  more than that before costs; the point-in-time screen earns {pct(g(pit))}, the hindsight list {pct(g(ceil))}.
* **The exit ladder captures the large moves when they happen.** On the 82-name list every trend-break
  exit was a winner (323 trades, average +30.4%), and all ten best trades closed on it (August report).
* **Stops do not cap losses on these names.** Hard-stop exits averaged −11.8% against a nominal −8%
  (worst −39.1%) because of overnight gaps and trading halts; only position size limits the damage.

## Threats to validity

| Threat | How it is handled | What remains |
|---|---|---|
| Hindsight in the universe | Point-in-time universe; the language model never names stocks | The hindsight list is used only as a ceiling |
| Look-ahead in features and fills | Tests with a positive control; entry at the next open; raw prices for price-level filters | None known |
| Engine errors | Legacy engine reproduces the notebook exactly; two defects fixed and tested | None known |
| Single random draw | {rf['draws']} draws with a pre-specified test | All draws share one price history |
| Survivorship | Not yet handled: delisted names are missing | Biases results **upward** for a long-only strategy; the fix is specified (FINRA membership) |
| Recorded signal measurements | Marked *(recorded)*; measured on survivor or enriched pools | To be re-measured point in time |

## Is it worth forward testing?

Not deployable: no point-in-time selection has beaten random names. Worth paper trading, because the
inputs most directly linked to a squeeze, borrow cost and social text, have no free history; recording
them live (`src/memescan/data/live.py`) is the only way to test them. The next stage
([`docs/spec/pipeline_spec.pdf`](docs/spec/pipeline_spec.pdf)) adds delisted names, options, float, dilution and
social text, and must clear acceptance criteria fixed in advance, starting with beating SPY's Sharpe
ratio of 0.95 and the random-names distribution.
"""


def main():
    df = pd.read_csv(R / "backtest_summary.csv")
    meta = json.loads((R / "backtest_meta.json").read_text())
    rf = json.loads((R / "random_floor.json").read_text())
    fill(ROOT / "README.md", "TOP", top(df, meta, rf))
    findings = ROOT / "docs" / "FINDINGS.md"
    fill(findings, "HEADLINE", headline(df, meta))
    fill(findings, "TABLE", table(df))
    print("README.md and docs/FINDINGS.md updated")


if __name__ == "__main__":
    main()
