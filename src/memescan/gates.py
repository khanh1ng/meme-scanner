"""Quality gates. Each exists because a specific defect was found and measured; each fails loudly.
See docs/RESEARCH_LOG.md for the defect behind every gate."""
import numpy as np
import pandas as pd


class GateError(AssertionError):
    pass


def calendar_index(idx, tz="America/New_York"):
    """Convert any timestamp index to a naive calendar-date index in New York time.
    Taking the date from naive UTC pushes bars stamped after 20:00 ET into the next day."""
    idx = pd.DatetimeIndex(idx)
    if idx.tz is not None:
        idx = idx.tz_convert(tz).tz_localize(None)
    return idx.normalize()


def join_with_coverage(left, right, min_coverage=0.5):
    """Gate 1. A price panel stamped 05:00 joined to a source stamped 00:00 produced ZERO overlapping
    days and silently turned every social feature into zero. Normalise both sides to calendar dates
    and refuse to proceed on low coverage."""
    left, right = left.copy(), right.copy()
    left.index, right.index = calendar_index(left.index), calendar_index(right.index)
    joined = left.join(right, how="left", rsuffix="_r")
    cov = joined[right.columns.intersection(joined.columns)].notna().any(axis=1).mean() if len(right.columns) else 0
    if cov < min_coverage:
        raise GateError(f"join coverage {cov:.1%} below {min_coverage:.0%}: check timestamps before trusting any feature")
    return joined


def corporate_action_ok(adv20_usd, atr_pct, price_raw, ret_20d):
    """Gate 2. Bankruptcy re-listings that reuse a ticker leave discontinuities (one series showed a
    52,648% 20-day gain). Rows outside plausible ranges are excluded from analysis."""
    if adv20_usd is None or not np.isfinite(adv20_usd) or adv20_usd < 10_000:
        return False
    if atr_pct is None or not np.isfinite(atr_pct) or not (0.005 < atr_pct < 1.0):
        return False
    if price_raw is None or not (0.10 <= price_raw <= 500):
        return False
    if ret_20d is None or abs(ret_20d) > 5.0:
        return False
    return True


def null_policy(value, policy, counter=None):
    """Gate 4. A short-interest gate returned False when data was absent, silently deleting 2021-2024
    and leaving 84 trades and a $389 loss that looked exactly like a strategy result.
    A missing value must be handled by a declared policy, and counted."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        if counter is not None:
            counter["null"] = counter.get("null", 0) + 1
        if policy == "allow":
            return True
        if policy == "block":
            return False
        raise GateError("null policy must be declared explicitly: 'allow' or 'block'")
    return None   # not null: the caller evaluates the value


def feature_sign(weight, ic, min_abs_ic=0.01):
    """Gate 5. Social level once entered the composite with a positive weight while its measured
    IC was -0.054. A weight's sign must match the measured IC, and |IC| must clear a floor."""
    if abs(ic) <= min_abs_ic:
        raise GateError(f"|IC| = {abs(ic):.3f} is noise; do not give this feature a weight")
    if np.sign(weight) != np.sign(ic):
        raise GateError(f"weight sign {np.sign(weight):+.0f} contradicts measured IC {ic:+.3f}")
    return True


def solvency(equity, position_size):
    """Gate 6. Fixed $10k sizing kept trading after cumulative losses exceeded capital, producing a
    'max drawdown' of -655%. New entries halt when equity cannot fund one position."""
    return "OK" if equity >= position_size else "HALT_NEW_ENTRIES"


def information_coefficient(feature, fwd_return):
    """Mean daily cross-sectional Spearman correlation. Prefer this to a backtest when they disagree:
    300 heavy-tailed trades cannot separate hypotheses (a random control once ranked first)."""
    f = feature.rank(axis=1)
    r = fwd_return.rank(axis=1)
    ok = f.notna() & r.notna()
    f, r = f.where(ok), r.where(ok)
    fc = f.sub(f.mean(axis=1), axis=0)
    rc = r.sub(r.mean(axis=1), axis=0)
    daily = (fc * rc).sum(axis=1) / np.sqrt((fc ** 2).sum(axis=1) * (rc ** 2).sum(axis=1))
    return float(daily.replace([np.inf, -np.inf], np.nan).dropna().mean())
