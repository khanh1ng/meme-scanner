import numpy as np
import pandas as pd
import pytest

from memescan import gates
from memescan.data.reddit import extract_tickers, burst_blocklist


def test_join_refuses_zero_coverage_from_mismatched_timestamps():
    days = pd.date_range("2021-01-04", periods=10, freq="B")
    left = pd.DataFrame({"close": range(10)}, index=days + pd.Timedelta(hours=5))
    right = pd.DataFrame({"mentions": range(10)}, index=days)
    raw = left.join(right)                       # the original defect: nothing matches
    assert raw["mentions"].isna().all()
    joined = gates.join_with_coverage(left, right)
    assert joined["mentions"].notna().all()
    with pytest.raises(gates.GateError):
        gates.join_with_coverage(left, right.shift(100, freq="D"))


def test_late_utc_bars_keep_their_new_york_date():
    idx = pd.DatetimeIndex(["2021-03-01 23:30"], tz="UTC")   # 18:30 in New York
    assert gates.calendar_index(idx)[0] == pd.Timestamp("2021-03-01")


def test_corporate_action_gate_rejects_relisting_discontinuity():
    assert gates.corporate_action_ok(5e6, 0.08, 4.0, 0.6)
    assert not gates.corporate_action_ok(5e6, 0.08, 4.0, 526.48)    # +52,648%
    assert not gates.corporate_action_ok(5e6, 0.08, 2980.0, 0.1)    # implausible level
    assert not gates.corporate_action_ok(None, 0.08, 4.0, 0.1)


def test_null_policy_must_be_declared_and_is_counted():
    cnt = {}
    assert gates.null_policy(None, "allow", cnt) is True
    assert gates.null_policy(np.nan, "block", cnt) is False
    assert cnt["null"] == 2
    assert gates.null_policy(3.0, "allow") is None
    with pytest.raises(gates.GateError):
        gates.null_policy(None, "reject")


def test_feature_sign_must_match_measured_ic():
    assert gates.feature_sign(+1.0, +0.061)
    with pytest.raises(gates.GateError):
        gates.feature_sign(+1.0, -0.054)          # the social-level defect
    with pytest.raises(gates.GateError):
        gates.feature_sign(+1.0, +0.004)          # noise


def test_solvency_halts_when_capital_cannot_fund_a_position():
    assert gates.solvency(10_000, 10_000) == "OK"
    assert gates.solvency(9_999, 10_000) == "HALT_NEW_ENTRIES"


def test_ticker_extraction_ignores_english_words():
    valid = {"BE", "ANY", "GME", "AMC"}
    text = "I will be buying any dip in $GME and AMC"
    assert extract_tickers(text, valid) == {"GME", "AMC"}
    assert extract_tickers(text.upper(), valid) == {"BE", "ANY", "GME", "AMC"}   # the old defect


def test_burst_blocklist_keeps_spiking_tickers():
    days = pd.date_range("2021-01-01", periods=60)
    word = np.full(60, 20.0)                      # flat chatter: an English word
    tick = np.full(60, 5.0); tick[30] = 400.0     # spikes on news: a ticker
    counts = pd.DataFrame({"THE": word, "GME": tick}, index=days)
    assert burst_blocklist(counts) == {"THE"}


def test_information_coefficient_sign():
    rng = np.random.default_rng(0)
    f = pd.DataFrame(rng.normal(size=(200, 30)))
    assert gates.information_coefficient(f, f + rng.normal(0, 1, f.shape)) > 0.5
    assert gates.information_coefficient(f, -f) < -0.99
