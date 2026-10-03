import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from memescan.panel import Panel  # noqa: E402


def make_panel(n_days=400, n_tick=25, seed=0):
    """Synthetic random-walk panel with occasional volume bursts and runs, enough to fire the
    universe and trigger rules. Only used for structural tests (look-ahead, engine mechanics)."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2019-01-01", periods=n_days)
    cols = [f"T{i:02d}" for i in range(n_tick)]
    ret = rng.normal(0, 0.04, (n_days, n_tick))
    burst = rng.random((n_days, n_tick)) < 0.01
    ret[burst] += 0.25
    close = 20 * np.exp(np.cumsum(ret, axis=0))
    opn = close * np.exp(rng.normal(0, 0.01, close.shape))
    high = np.maximum(opn, close) * (1 + rng.random(close.shape) * 0.03)
    low = np.minimum(opn, close) * (1 - rng.random(close.shape) * 0.03)
    vol = rng.lognormal(13, 0.4, close.shape) * np.where(burst, 6.0, 1.0)
    f = lambda a, t: pd.DataFrame(a, index=idx, columns=cols).astype(t)  # noqa: E731
    return Panel(f(opn, "float32"), f(high, "float32"), f(low, "float32"), f(close, "float32"), f(vol, "float64"))


@pytest.fixture
def panel():
    return make_panel()
