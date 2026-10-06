"""r/wallstreetbets history from the Arctic Shift archive, and ticker extraction.

Two defects shaped this module:
* Upper-casing whole sentences turned "will be" into ticker BE and "any" into ANY: 46% of all
  "mentions" were English words. Only $CASHTAGS and tokens that were ALREADY upper-case in the
  source text are candidates, and a burst-based blocklist removes words that never spike.
* A count cannot separate 100 posts by 100 people from 100 posts by one account. Store full text
  and a hashed author when the pass is re-run (see the spec, Module 1).

Reddit's own public JSON returns 403 to automated agents and Pushshift is discontinued.
"""
import re
import time
from datetime import timedelta

import pandas as pd
import requests

from .. import config as C

CASHTAG = re.compile(r"\$([A-Z]{1,5})\b")
UPPER_WORD = re.compile(r"\b([A-Z]{2,5})\b")


def fetch_day(day, subreddit="wallstreetbets", max_pages=4, sleep_ok=2.0, sleep_bad=20.0):
    """Titles and bodies of posts created on `day` (UTC). Retries with backoff on 422/429/503."""
    texts, after = [], f"{day}T00:00:00Z"
    before = f"{day + timedelta(days=1)}T00:00:00Z"
    for _ in range(max_pages):
        params = {"subreddit": subreddit, "after": after, "before": before, "limit": 100,
                  "fields": "title,selftext,created_utc,author", "sort": "asc"}
        data = None
        for attempt in range(6):
            try:
                r = requests.get(C.EP_ARCTIC, params=params, headers=C.BROWSER_UA, timeout=45)
                if r.status_code == 200:
                    data = r.json().get("data") or []
                    break
                if r.status_code in (422, 429, 503):
                    time.sleep(sleep_bad * (attempt + 1))
                    continue
                return texts
            except requests.RequestException:
                time.sleep(sleep_bad * (attempt + 1))
        if not data:
            return texts
        texts += [f"{p.get('title', '')} {p.get('selftext', '')}" for p in data]
        last = data[-1].get("created_utc")
        if not last:
            break
        after = pd.to_datetime(last, unit="s").strftime("%Y-%m-%dT%H:%M:%SZ")
        time.sleep(sleep_ok)
    return texts


def extract_tickers(text, valid, blocklist=frozenset()):
    """Cashtags, plus upper-case tokens as written. Never upper-case the sentence first."""
    cands = set(CASHTAG.findall(text)) | set(UPPER_WORD.findall(text))
    return {c for c in cands if c in valid and c not in blocklist}


def burst_blocklist(daily_counts, burst_max=10.0, min_total=50):
    """Tokens that never spike are English words, not tickers.

    daily_counts: DataFrame indexed by day, one column per token.
    burst = max daily count / median daily count over days with any mention. Real tickers spike on
    news; words are flat. A first attempt correlated each token with total chatter and wrongly
    flagged GME and AMC, which drive the total. The burst statistic does not have that failure."""
    nz = daily_counts.where(daily_counts > 0)
    burst = nz.max() / nz.median()
    total = daily_counts.sum()
    return set(burst[(burst < burst_max) & (total > min_total)].index)
