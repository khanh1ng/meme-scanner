"""Constants and environment. Credentials come from the environment only; nothing is hard-coded.

Parameters marked FIXED are held constant for the whole study. Their comments record where the
value came from, including when it was chosen on data later found to be biased (see docs/RESEARCH_LOG.md).
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(os.getenv("MEMESCAN_CACHE", ROOT / "data"))
RESULTS = ROOT / "results"

# ---- credentials (environment only) -------------------------------------------------------
def alpaca_headers():
    key = os.getenv("APCA_API_KEY_ID")
    secret = os.getenv("APCA_API_SECRET_KEY")
    if not key or not secret:
        raise RuntimeError("Set APCA_API_KEY_ID and APCA_API_SECRET_KEY in the environment (see .env.example).")
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}


LLM_KEY = os.getenv("DEEPSEEK_API_KEY")
LLM_BASE = os.getenv("DEEPSEEK_BASE_URL", "https://openrouter.ai/api/v1")
LLM_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek/deepseek-v4-flash")
LLM_ENABLED = False          # the deterministic pipeline is evaluated without the model

# Keyless sources reject the default python-requests agent with HTTP 403.
BROWSER_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
              "Accept": "application/json, text/plain, */*"}

# ---- endpoints ----------------------------------------------------------------------------
EP_ASSETS = "https://api.alpaca.markets/v2/assets"
EP_BARS = "https://data.alpaca.markets/v2/stocks/bars"
EP_OPT_CONTRACTS = "https://paper-api.alpaca.markets/v2/options/contracts"
EP_OPT_BARS = "https://data.alpaca.markets/v1beta1/options/bars"
EP_FINRA = "https://cdn.finra.org/equity/otcmarket/biweekly/shrt{yyyymmdd}.csv"
EP_ARCTIC = "https://arctic-shift.photon-reddit.com/api/posts/search"
EP_APEWISDOM = "https://apewisdom.io/api/v1.0/filter/{flt}/page/{page}"
EP_STOCKTWITS = "https://api.stocktwits.com/api/2/streams/symbol/{sym}.json"
EP_IBORROW = "https://iborrowdesk.com/api/ticker/{sym}"
EXCHANGES = ("NYSE", "NASDAQ", "AMEX", "ARCA", "BATS")

# ---- portfolio ----------------------------------------------------------------------------
CAPITAL = 100_000.0
POS_SIZE = 10_000.0
MAX_POS = 10                 # 10 x $10k = full capital, no compounding

# ---- layer 0: tradability, applied identically to strategy and controls --------------------
LIQ_FLOOR = 1_000_000.0      # 20-day average dollar volume through t-1

# ---- layer 1: universe (v2 rules, point in time) -------------------------------------------
DD_FROM_ATH = -0.50          # at least 50% below the all-time high (history from 2016)
MEME_RUN = 0.50              # a past "meme event": +50% within the next 20 sessions
MEME_WINDOW = 20

# ---- layer 2: ignition trigger, evaluated at the close of day t ----------------------------
RVOL_MIN = 2.0               # sweep 1.75..3.0 gave a plateau; chosen on the biased pool
EXT_CAP = 0.50               # max distance above MA20; chosen by ablation on the biased pool
MOM5_MIN = 0.05

# ---- exits ---------------------------------------------------------------------------------
HARD_STOP = 0.08             # 12% tested better but the gap was within one trade; kept to avoid fitting
EARLY_DAYS = 2               # exit if the trade has not gained 3% after 2 sessions
EARLY_MFE = 0.03
ATR_WIN = 14
ATR_MULT = 3.0
MA_EXIT = 10
MAX_HOLD = 60

# ---- costs: square-root impact, one way, capped ---------------------------------------------
COST_FIXED = 0.001
COST_IMPACT = 0.1
COST_CAP = 0.05

# ---- publication lags ----------------------------------------------------------------------
SI_LAG_DAYS = 12             # FINRA short interest is disseminated ~8 business days after settlement

SEED = 7
