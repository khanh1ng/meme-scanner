"""No decision may change when data after the decision day is deleted.

The universe for day t and the trigger at the close of t are recomputed on a panel truncated at T and
compared with the full-panel run for every day up to T. A test that never fails proves nothing, so a
positive control injects a one-day leak and the same comparison must catch it."""
import numpy as np
import pandas as pd

from memescan import universe, trigger
from memescan.panel import Panel


def _cuts(p, k=12):
    d = p.dates
    return [d[i] for i in np.linspace(80, len(d) - 2, k).astype(int)]


def test_universe_and_trigger_do_not_look_ahead(panel):
    full_u, full_t = universe.pit_universe(panel), trigger.ignition(panel)
    assert full_u.values.any() and full_t.values.any(), "synthetic panel must exercise the rules"
    for T in _cuts(panel):
        p_t = panel.truncate(T)
        assert universe.pit_universe(p_t).equals(full_u.loc[:T])
        assert trigger.ignition(p_t).equals(full_t.loc[:T])


def test_positive_control_catches_a_one_day_leak(panel):
    def leaky(p):   # uses tomorrow's close: exactly the bug the test exists to catch
        return p.close.shift(-1) > p.close
    full = leaky(panel)
    flagged = sum(not leaky(panel.truncate(T)).equals(full.loc[:T]) for T in _cuts(panel))
    assert flagged == len(_cuts(panel))


def test_meme_event_is_knowable_only_after_its_peak():
    c = np.array([10, 10, 11, 13, 16, 18, 17, 15, 14, 14, 14], dtype=float)
    ev = universe.meme_events(c)
    assert len(ev) == 1
    assert ev[0]["ignition"] == 0 and ev[0]["peak"] == 5 and ev[0]["knowable_from"] == 6
    idx = pd.bdate_range("2020-01-01", periods=len(c))
    df = pd.DataFrame({"X": c}, index=idx).astype("float32")
    p = Panel(df, df, df, df, df.astype("float64") * 1e6)
    flag = universe.prior_meme_flag(p)["X"]
    assert not flag.iloc[:6].any() and flag.iloc[6:].all()
