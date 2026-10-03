"""Optional language-model overlay. Disabled by default; the pipeline is evaluated without it.

The central lesson of this project: the original 82-name universe came from asking a model to name
potential meme stocks. A model trained after the fact already knew the answer, and that single call
invalidated every backtest built on it.

    A model may PROCESS the past. It must never RECALL the past.

So the model only converts existing posts into numbers, only for names the deterministic pipeline has
already selected, once per (ticker, day) after the close, cached. It can reorder, never add, a name.
"""
import json

import requests

from . import config as C

SYSTEM_PROMPT = """You are a text classifier for financial social media. You will be given recent
posts about one ticker from one day. Return only a JSON object, no prose. Fields:
conviction    integer 0 to 3. 0 passing mentions, 1 opinion, 2 specific reasoning or target,
              3 authors state positions held, with size or entry
catalyst      short phrase naming a specific expected event, or null
coordination  true when posts read as coordinated promotion rather than independent opinion
novelty       true when this reads as a new thesis rather than continuation of an old one
time_horizon  one of: intraday, days, weeks, months, unclear
You must not use any knowledge of what happened to this stock after these posts were written.
Judge only what the text says. Do not name any ticker that does not appear in the text."""


def classify(ticker, day, texts, cache_path=None):
    if not C.LLM_ENABLED or not C.LLM_KEY:
        return None
    cache_path = cache_path or (C.CACHE / "llm_context.json")
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    key = f"{ticker}|{day}"
    if key in cache:
        return cache[key]
    payload = {"model": C.LLM_MODEL, "temperature": 0.0, "max_tokens": 250,
               "response_format": {"type": "json_object"},
               "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": "\n".join(texts)[:8000]}]}
    try:
        r = requests.post(C.LLM_BASE + "/chat/completions", json=payload, timeout=30,
                          headers={"Authorization": f"Bearer {C.LLM_KEY}", "Content-Type": "application/json"})
        out = json.loads(r.json()["choices"][0]["message"]["content"])
    except (requests.RequestException, KeyError, ValueError):
        return None   # never abort the pipeline on a model failure
    cache[key] = out
    cache_path.write_text(json.dumps(cache))
    return out
