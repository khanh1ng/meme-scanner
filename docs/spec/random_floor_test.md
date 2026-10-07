# Random-names floor as a distribution: specification (fixed before the run)

Committed before the script was written or any draw was run.

## Question

Stage 2 compares the point-in-time (PIT) screen with **one** draw of random names. One draw cannot
say whether the PIT result is distinguishable from random selection, or whether the gap between
the hindsight list and random names is larger than draw-to-draw noise. This test replaces the
single draw by a distribution.

## Design

* 200 random-names universes, seeds 1 to 200. Each day, each draw picks at random from the same
  tradable pool as many names as the PIT universe holds on average, as `controls.random_floor` does.
* Everything else is identical to Stage 2: the same trigger, entry at the next open, exits,
  sizing, square-root costs, and the corrected engine.
* Statistics for every draw: mean net return per trade, number of trades, final equity and Sharpe ratio.

## Tests and how they are read (fixed now)

* **PIT selection skill.** One-sided p-value = (1 + number of draws whose mean net return per trade
  is at least the PIT value) / 201. PIT skill is supported only if p < 0.05.
* **Value of selection (hindsight ceiling).** The same p-value for the hindsight list. If p < 0.05,
  the gap between the ceiling and random selection is not draw-to-draw noise.
* The PIT and hindsight percentiles in the random distribution are reported in both cases.

## Limits stated now

* The draws share one price history, so the test measures selection skill given that history, not
  the uncertainty of the period itself.
* The hindsight list is invalid as a strategy; it only measures how much selection can matter.
