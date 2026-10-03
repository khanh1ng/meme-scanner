# Findings

## 1. The reproducible backtest

`scripts/run_backtest.py` rebuilds the v2 experiment from the cached daily panel. Every universe is
run with the research notebook's engine (`legacy`) and with the corrected engine. The `legacy` rows
match the notebook's saved output (`archive/notebooks/06_scanner_v2_pit.ipynb`) to every printed digit,
which is how the port was verified.

<!-- HEADLINE:START -->
On 2,673 sessions (2016-01-04 to 2026-08-20) and 10,236 tickers, with costs and next-open fills, the point-in-time strategy turns $100,000 into $1,151 (Sharpe -0.52); a universe of random names drawn from the same tradable pool ends at $2,031 (Sharpe -0.53). Only the deliberately biased hindsight list makes money ($247,310, Sharpe 0.43). The research notebook's own engine reported Sharpe -0.19 for the same universe; the two defects fixed in `src/memescan/backtest.py` move it to -0.52.
<!-- HEADLINE:END -->

<!-- TABLE:START -->
| Engine | Universe | Trades | Win rate | Mean net return / trade | Mean cost / trade | Final equity | CAGR | Sharpe | Max DD | P&L without top 10 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| legacy | PIT universe | 790 | 31.8% | -1.15% | 1.23% | $9,466 | -19.9% | -0.19 | -64.0% | −$162,089 |
| legacy | Hindsight 82, same filter (ceiling) | 1207 | 31.1% | +1.22% | 0.70% | $247,310 | +8.9% | 0.53 | -49.2% | −$80,255 |
| legacy | Random names, same filter (floor) | 883 | 35.7% | -1.02% | 1.06% | $9,532 | -19.8% | -0.60 | -59.3% | −$126,665 |
| legacy | PIT universe, no costs | 2521 | 36.4% | -0.36% | 0.00% | $9,715 | -19.7% | 0.26 | -53.3% | −$252,228 |
| corrected | PIT universe | 819 | 32.0% | -1.21% | 1.22% | $1,151 | -34.3% | -0.52 | -99.0% | −$169,788 |
| corrected | Hindsight 82, same filter (ceiling) | 1207 | 31.1% | +1.22% | 0.70% | $247,310 | +8.9% | 0.43 | -55.0% | −$80,255 |
| corrected | Random names, same filter (floor) | 895 | 35.1% | -1.09% | 1.06% | $2,031 | -30.7% | -0.53 | -99.1% | −$134,166 |
| corrected | PIT universe, no costs | 2527 | 36.3% | -0.39% | 0.00% | $2,277 | -29.9% | -0.19 | -98.4% | −$259,665 |
<!-- TABLE:END -->

**Rules (all point in time).**

* Universe for day t, from data through t−1:
  * either at least 50% below the all-time high (history from 2016) and back above the 50-day average,
  * or a past meme event (+50% within 20 sessions), usable only from the day after its peak.
* Tradability: 20-day dollar volume of at least $1M, applied identically to every universe.
* Trigger at the close of day t:
  * relative volume ≥ 2;
  * close above the typical price, above yesterday's close and above the 20-day average;
  * 5-day momentum above 5%;
  * no more than 50% above the 20-day average.
* Entry at the open of t+1.
* Exits:
  * −8% stop, filled at the open on a gap;
  * no progress (under +3% after 2 sessions);
  * 3×ATR trailing stop;
  * break of the 10-day average once in profit;
  * 60-session cap.
* Costs: 0.1% plus 0.1·√(position / dollar volume) each way, capped at 5%.
* Sizing: $10k per position, at most 10 positions, no compounding.

**Reading the table.**

* **The point-in-time strategy loses money before costs as well as after.** The "no costs" row is
  also negative, so the failure is in selection, not in friction.
* **It does no better than random names.** Names drawn at random from the same pool end in the same
  place, which is what a strategy with no selection skill would show. No formal test was run; with a
  result this negative, none is needed to reject the strategy.
* **Only the hindsight list works.** That list is invalid by construction (Research log, defect 1).
  It is shown for scale.
* **Fixing the engine made the result worse, not better.** The legacy engine let losses that had not
  happened yet stop new entries, and its curve skipped entry-day moves and stop fills. Fixing both made
  the point-in-time result worse. This is why defects 18 and 19 are listed even though they were found
  after the research ended.
* **The legacy Sharpe and the legacy final equity contradict each other.** The legacy curve ends far
  from the realised P&L (the `curve_end_minus_final` column in `results/backtest_summary.csv`), so its
  Sharpe and drawdown described a different portfolio from the one its final equity did.

**Not yet fixed in this run.** The symbol master holds stocks still listed today, so delisted names
are missing. For a long-only strategy that biases results **upwards**. The fix (point-in-time listing
from FINRA snapshots, with Alpaca bars for delisted names) is specified but not built.

## 2. Findings carried from the research notebooks

Measured in `archive/`. They were measured on survivor universes, and in some cases on the biased
195-name pool, so they are observations to re-test, not established properties.

### Base rates

Event: a gain of +100% or more within 20 sessions. Denominator: 8,967,916 symbol-days. Base rate 0.68%.

| Filter | Hit rate | Lift |
|---|---:|---:|
| none | 0.68% | 1.00x |
| 20-day dollar volume ≥ $1M | 0.37% | 0.54x |
| 20-day dollar volume ≥ $5M | 0.24% | 0.35x |
| 20/60-day volume build ≥ 1.3 | 1.65% | 2.40x |
| 20-day return > +20% | 1.94% | 2.84x |
| ATR ≥ 8% of price | 3.51% | 5.12x |
| ≥ 90% below all-time high | 3.78% | 5.53x |
| ATR ≥ 12% of price | 5.52% | 8.05x |
| combined (all of the above that lift, plus $1M liquidity) | 8.35% | 12.19x |

**Absolute thresholds are unusable in a walk-forward.** The combined absolute gate selects 3 names a
day in 2021 and 23 in 2025, an eightfold drift. Cross-sectional percentiles (top 10% by ATR and by
20-day return, drawdown above the median) give about 40 names a day with a coefficient of variation
of 0.27 and a lift of 6.31x. That is the specified replacement.

**More price-and-volume gates add nothing.** Gap frequency has a standalone lift of 5.19x but 0.99x
on top of the base gate. It selects the same names as high ATR.

### Information coefficients

Spearman correlation with 20-day forward return, as reported in the August report (Section 8). The
195-name pool contains the 82 hindsight names, so these are observations, not properties:

| Feature | IC | Sample | Reading |
|---|---:|---|---|
| distance from all-time high | +0.165 | 195-name pool, price only | less fallen is better |
| prior meme events | −0.152 | 195-name pool, price only | names that already ran keep falling |
| OTM call volume (level) | +0.061 | 110 names, 2024 onward | strongest positive found |
| social mention level | −0.054 | 159 names, 2021–2026 | already crowded means late |
| social mention acceleration | +0.025 | 159 names, 2021–2026 | weak |
| dollar volume surge (benchmark) | +0.022 | 195-name pool | weak |
| short-interest change (FINRA) | ~0 | 195-name pool | no signal at bi-monthly frequency |

### Exits (1,167 trades; August report, Section 5.1, on the 82-name list)

| Exit | Trades | Win rate | Mean return | P&L |
|---|---:|---:|---:|---:|
| trend break | 323 | 100% | +30.4% | +$981,781 |
| trailing stop | 20 | 60% | +41.0% | +$81,975 |
| max hold | 5 | 40% | +0.6% | +$275 |
| no progress | 419 | 20% | −2.6% | −$109,988 |
| hard stop | 400 | 0% | −11.8% | −$473,368 |

**The ten best trades all exited on a trend break, and the ten worst on the hard stop.** Seven of the
worst exited within 2 sessions, with losses of 22.8% to 39.1% against a nominal 8%: overnight gaps
and limit-up/limit-down halts.

## 3. Values from the earlier reports that this repository does not regenerate

The August report ([`docs/reports/2026-08_without_the_language_model.pdf`](reports/2026-08_without_the_language_model.pdf))
and the specification (`docs/spec/pipeline_spec.pdf`, Module 9) quote these values:

| Run | Source | Sharpe | Final equity |
|---|---|---:|---:|
| SPY buy and hold | specification | 0.95 | |
| 82 names from the language model, no language model in the decision path | August report, Section 5 | 1.07 | $580,674 |
| Screen v1 (short interest, top 150) | August report, Section 7.1 | 0.61 | $212,817 |
| Random 150 | August report, Section 7.1 | 0.28 | $124,361 |
| Random selection of 82 names | August report, Section 6.3 | 0.26 | $123,401 |
| Screen v2 (volatility floor, top 150) | August report, Section 7.2 | | −$130,427 |

Why they differ from section 1:

* the 82-name list was chosen with hindsight (Research log, defect 1);
* screen v1 ran on surviving symbols with a 12-day FINRA lag; the report itself traces its profit to
  dual-listed Canadian banks and utilities whose days to cover is inflated by thin US volume, and
  correcting that (screen v2) turns expectancy to −1.66%;
* the notebook run behind these values was not preserved. `archive/scripts/compare_versions.py` is a
  different comparison (top 30 names a day, no cost model), so its saved output does not match them.

None of these values is regenerated here. The table in section 1 is the only backtest result this
repository stands behind. Its message agrees with the August report's own conclusion and is
stronger: no valid version beats SPY's 0.95, and the full-universe version with costs loses money.
