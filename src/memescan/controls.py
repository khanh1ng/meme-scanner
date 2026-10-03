"""Comparison universes. A control must randomise the same thing the strategy chooses.

The strategy chooses NAMES, so the floor draws names at random each day from the same tradable pool.
An earlier null test randomised entry TIMING inside a fixed (and invalid) universe and passed at
p = 0.025; it could not detect the universe bias because it held the universe fixed.
"""
import numpy as np
import pandas as pd

from . import config as C


def random_floor(tradable_mask, n_per_day, seed=C.SEED):
    rng = np.random.default_rng(seed)
    out = pd.DataFrame(False, index=tradable_mask.index, columns=tradable_mask.columns)
    t = tradable_mask.values
    for i in range(len(out)):
        ok = np.where(t[i])[0]
        if len(ok):
            out.iloc[i, rng.choice(ok, size=min(n_per_day, len(ok)), replace=False)] = True
    return out


def hindsight_ceiling(tradable_mask, names):
    """A deliberately biased universe of names known to have run. For SCALE only: never an
    achievable result. It receives the same tradability filter as everything else."""
    out = pd.DataFrame(False, index=tradable_mask.index, columns=tradable_mask.columns)
    for s in set(names) & set(out.columns):
        out[s] = True
    return out & tradable_mask
