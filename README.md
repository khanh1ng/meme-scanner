# meme-scanner

[![tests](https://github.com/khanh1ng/meme-scanner/actions/workflows/tests.yml/badge.svg)](https://github.com/khanh1ng/meme-scanner/actions/workflows/tests.yml)

**Can meme-stock squeezes be selected before they run, using only what was known at the time?**

*Research June–September 2026 (reports dated July 30, August 21 and September 18); packaged and
published October 2026.*

<!-- TOP:START -->
**Summary.** The project asks whether meme-stock squeezes can be selected before they run using
only information available at the time. The answer so far: the execution layer converts good selection into profit, selection decides the result, and price and volume alone do not select. With identical trading rules,
names that later squeezed earn +1.22% per trade after costs, above all 200 random-name
draws (p = 0.005); the point-in-time price-and-volume screen earns −1.21%, below 95.5% of
the random draws (p = 0.96 for skill). Before costs its trades earn +0.02%
per trade; costs of about 1.2% per trade in these illiquid names decide the sign. The inputs
most directly linked to a squeeze (borrow cost, options positioning, float and dilution, social text)
are specified for the next stage and not yet tested.

## Hypotheses and verdicts

| | Hypothesis | Test | Evidence | Verdict |
|---|---|---|---|---|
| H1 | A list of meme stocks named by a language model is a valid universe | Same rules on the list and on random names (August report) | +3.12% per trade on the list, −0.60% on 113 random names; a model trained after 2021 already knows which stocks squeezed | **Rejected**: hindsight bias |
| H2 | The execution layer turns good selection into profit | Hindsight list against 200 random-name draws ([spec](docs/spec/random_floor_test.md)) | +1.22% per trade against random −0.87% [−1.19%, −0.73%]; p = 0.005 | **Supported** |
| H3 | A point-in-time price-and-volume screen selects better than random | Same test for the screen | −1.21% per trade, below 95.5% of random draws; p = 0.96 | **Not supported** |
| H4 | High short interest marks the names that squeeze | Lift of days-to-cover on the chance of a +100% move in 20 sessions *(recorded, survivor data)* | Days to cover ≥ 3: 0.60x; below 2: 1.44x; median change in short interest before large moves 0% | **Not supported** at bi-monthly frequency |
| H5 | A volume spike marks the start of a squeeze | Relative volume on the day a +100% move begins *(recorded)* | Median 0.97x; what precedes it is a slow build (20/60-day volume 1.28x) | **Not supported**: a spike trigger is late |
| H6 | Structural screens raise the base rate of large moves | Hit rate of +100% in 20 sessions, 8,967,916 symbol-days *(recorded, survivor data)* | 0.68% base rate; combined gate 8.35% (12.19x); percentile version 6.31x with a stable universe | **Supported** on survivor data; to re-test point in time |
| H7 | Options positioning and social text carry selection information | Information coefficients with 20-day returns *(recorded, enriched pool)* | Out-of-the-money call volume +0.061 (110 names, 2024+); mention level −0.054 | **Untested at scale** |

## Stage 2 results (corrected engine, after costs)

| Selection (same trigger, entry, exits, sizing and costs) | Trades | Win rate | Mean gross / trade | Mean cost / trade | Mean net / trade |
|---|---:|---:|---:|---:|---:|
| Names that later squeezed (hindsight list; upper bound, not a strategy) | 1,207 | 31.1% | +1.92% | 0.70% | +1.22% |
| Random names from the same tradable pool (seed 7) | 895 | 35.1% | −0.04% | 1.06% | −1.09% |
| Point-in-time price-and-volume screen | 819 | 32.0% | +0.02% | 1.22% | −1.21% |
| Random names, 200 draws: median [5th, 95th percentile] | | | | | −0.87% [−1.19%, −0.73%] |

2,673 sessions (2016-01-04 to 2026-08-20), 10,236 tickers; entry at the next open; costs 0.1% plus a
square-root impact term each way. Full table, both engines and drawdowns: [`docs/FINDINGS.md`](docs/FINDINGS.md).

## Mechanism

* **Costs set the bar selection must clear.** These names are illiquid: a round trip costs
  1.22% per trade on average for the screen and 0.70% for the hindsight list. Selection has to earn
  more than that before costs; the point-in-time screen earns +0.02%, the hindsight list +1.92%.
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
| Single random draw | 200 draws with a pre-specified test | All draws share one price history |
| Survivorship | Not yet handled: delisted names are missing | Biases results **upward** for a long-only strategy; the fix is specified (FINRA membership) |
| Recorded signal measurements | Marked *(recorded)*; measured on survivor or enriched pools | To be re-measured point in time |

## Is it worth forward testing?

Not deployable: no point-in-time selection has beaten random names. Worth paper trading, because the
inputs most directly linked to a squeeze, borrow cost and social text, have no free history; recording
them live (`src/memescan/data/live.py`) is the only way to test them. The next stage
([`docs/spec/pipeline_spec.pdf`](docs/spec/pipeline_spec.pdf)) adds delisted names, options, float, dilution and
social text, and must clear acceptance criteria fixed in advance, starting with beating SPY's Sharpe
ratio of 0.95 and the random-names distribution.

<!-- TOP:END -->

## Reports

The project produced three written reports. Each records what was measured at that stage; the values
below are quoted exactly as each report states them. Only the Stage 2 summary below is
regenerated by this repository.

| Report | Date | What it reports | Status today |
|---|---|---|---|
| [Design, pipeline, findings and decisions](docs/reports/2026-07_design_and_findings.pdf) | Jul 30, 2026 | Filter ablation ending at $519,858 from $100,000; reactive entries +$618,307, no-meme false positives −$409,657 (46% of trades); median detection lag +16 days | Superseded. The report itself flags survivorship and no costs; the universe was later found to be chosen with hindsight |
| [Testing whether the language model and the missing data are needed](docs/reports/2026-08_without_the_language_model.pdf) | Aug 21, 2026 | Without the language model, on the 82-name list: 1,167 trades, Sharpe 1.07, Sortino 1.49, max drawdown −19.4%, $580,674. Point-in-time screen v1 (short interest, top 150): Sharpe 0.61, $212,817, against random 0.28. Screen v2 (artifact removed): expectancy −1.66% | The report itself identifies the 82-name bias and calls screen v1 not deployable. Its screens ran on a narrower survivor pool; the v2 pipeline adds square-root costs and a point-in-time universe on every surviving US stock: see Stage 2 below |
| [Pseudocode specification for walk-forward testing](docs/spec/pipeline_spec.pdf) | Sep 18, 2026 | The next experiment: point-in-time listing with delisted names, 7-fold walk-forward, acceptance criteria. The bar to clear is SPY's Sharpe of 0.95 | Not yet run |

[`docs/RESEARCH_LOG.md`](docs/RESEARCH_LOG.md) traces every step from the hindsight-biased Sharpe of 1.07 to
the point-in-time baseline, and why each change was made.

## What is worth reading

* [`docs/RESEARCH_LOG.md`](docs/RESEARCH_LOG.md): the 19 defects, each with how it showed up, what
  it did to the numbers, and where the guard now lives. Highlights:
  * a timestamp mismatch in a join made every social feature zero, and the conclusion "social data
    is useless" was an artifact of that join;
  * filling at the signal bar's close overstated expectancy by 38%;
  * split-adjusted price filters read future reverse splits;
  * a null test that randomised the wrong thing passed at p = 0.025;
  * the backtest engine's own solvency check used P&L that had not happened yet.
* [`docs/spec/pipeline_spec.pdf`](docs/spec/pipeline_spec.pdf): a 21-page, module-by-module
  pseudocode specification for the walk-forward test. It covers:
  * point-in-time listing that includes delisted names;
  * leakage assertions;
  * limit-up/limit-down halts, theme concentration limits and graceful degradation;
  * staged paper-to-live rollout;
  * acceptance criteria fixed before the run.
* [`docs/spec/build_spec_v3.md`](docs/spec/build_spec_v3.md): the companion build specification (v3, plain
  text): every data source with endpoint, plan, rate limit and publication lag, and the pipeline in
  prose. The pseudocode PDF supersedes it where they differ.
* [`src/memescan/gates.py`](src/memescan/gates.py): one function per defect class, each with the
  defect it exists for in its docstring.

## Layout

```
src/memescan/
  config.py        constants; credentials from the environment only
  data/            alpaca (bars, options), finra (short interest), reddit (Arctic Shift), live (ApeWisdom, StockTwits, iBorrowDesk)
  panel.py         long bars -> wide date x ticker panel
  universe.py      layer 0 tradability, layer 1 point-in-time universe, meme events knowable only after their peak
  trigger.py       layer 2 ignition trigger at the close
  backtest.py      next-open entry, gap-aware stops, square-root costs, daily mark to market (legacy + corrected)
  controls.py      random-names floor, hindsight ceiling
  gates.py         quality gates, information coefficient
  llm.py           optional overlay, off by default: processes posts, never recalls the past
scripts/           fetch_universe, fetch_finra, fetch_reddit, fetch_options, run_backtest, run_random_floor, report, check_secrets
tests/             look-ahead (with a positive control), engine mechanics, gates, no credentials in the repo
docs/              research log, findings, reports (Jul and Aug 2026), specifications (pseudocode pdf + tex, build spec v3)
archive/           the original notebooks and scripts: credentials removed, outputs cleared, marked superseded
results/           output of run_backtest.py
```

## Running it

```bash
pip install -e ".[dev]"
cp .env.example .env              # fill in APCA_API_KEY_ID / APCA_API_SECRET_KEY, then load it
python scripts/fetch_universe.py  # ~18.5M daily bars, about an hour, resumable
python scripts/run_backtest.py    # ~10 minutes
python scripts/run_random_floor.py  # 200 random-name draws, ~40 minutes on 6 cores
python scripts/report.py          # writes the generated summary and the findings table from results/
pytest
```

Price data comes from Alpaca's SIP feed (the Algo Trader Plus plan). FINRA, Arctic Shift and
ApeWisdom need no key. Every script only reads data and never places an order. `scripts/check_secrets.py`
fails if anything resembling a credential is in the tree.

## License

MIT
