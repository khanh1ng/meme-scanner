================================================================================
MEME STOCK SCANNER - FULL PIPELINE SPECIFICATION
Walk-forward testable, point-in-time correct, LLM sentiment included
Version 3.0 | 2026-09-10
================================================================================

PART 0 - HOW TO READ THIS
--------------------------------------------------------------------------------
This document is a build specification, not a summary. A reader with no prior
knowledge of the project should be able to rebuild the entire pipeline from it.

Notation:
  t            = the trading day a decision is made
  t-1          = previous trading session (the last data we are allowed to use)
  close[t]     = official closing price of day t
  x.shift(1)   = the value of x as of the previous session
  z(x)         = cross-sectional z-score, computed across all symbols ON THE SAME
                 DAY. This never looks forward in time and is always safe.
  pct(x, q)    = the q-th percentile of x, computed over a TRAILING window only.
                 Computing this over the whole sample is look-ahead. See PART 7.

The single rule that governs everything:
  At any moment in the simulation, the code may only touch data that a live
  trader would physically have had at that moment, including publication delays.

Why this document exists:
  An earlier version of this system reported a Sharpe ratio of 1.07 and final
  equity of $580,674. That result was invalid. The universe of 82 names had been
  produced by asking a language model to list potential meme stocks. A model
  trained through 2026 already knows which stocks became meme stocks, so the
  request returned the answer rather than a screen. Rebuilding the universe
  point-in-time dropped the Sharpe ratio to 0.61, which is below SPY buy-and-hold
  at 0.95 over the same window. Every guard in this document exists because a
  specific error was found and measured.


================================================================================
PART 1 - DATA SOURCES
================================================================================

--------------------------------------------------------------------------------
1.1 PRICE AND VOLUME (primary, required)
--------------------------------------------------------------------------------
Provider    : Alpaca Market Data
Plan        : Algo Trader Plus
Cost        : USD 99 per month
Rate limit  : 10,000 requests per minute
Auth        : HTTP headers
              APCA-API-KEY-ID     : <ALPACA_KEY_ID>
              APCA-API-SECRET-KEY : <ALPACA_SECRET>

Daily bars:
  GET https://data.alpaca.markets/v2/stocks/bars
      symbols     = up to 100 comma-separated tickers per request
      timeframe   = 1Day
      start       = 2016-01-01     (see note on why 2016)
      end         = <today>
      feed        = sip            (full consolidated tape, not iex)
      adjustment  = split          (see CRITICAL note below)
      limit       = 10000
      page_token  = <next_page_token from previous response>

Intraday bars (Layer 2 confirmation only):
  Same endpoint, timeframe = 15Min. Available from 2016 on this plan.

CRITICAL - two separate price series are required:
  adjustment=split  -> use for ALL RETURN calculations. Splits cancel out of
                       returns, so returns are correct.
  adjustment=raw    -> use for ALL PRICE-LEVEL filters (for example "price
                       under 10 dollars").
  Reason: Alpaca adjusts historical prices backward. A 1-for-100 reverse split
  in 2023 multiplies the displayed 2021 price by 100. One symbol displayed a
  price of 2.98 trillion dollars in 2016. 463 symbols displayed a price above
  1000 dollars while actually trading as penny stocks, which is 7.8 percent of
  all detected events. Filtering on the adjusted price level therefore uses
  knowledge of a future corporate action. This is a real look-ahead leak and it
  is currently unfixed in the existing code base.

Why start at 2016:
  The screen uses drawdown from the all-time high. If the history begins in 2021
  the "all-time high" is truncated and the measure is meaningless. Five years of
  lead-in makes the high meaningful before the 2021 meme era begins.

--------------------------------------------------------------------------------
1.2 SYMBOL MASTER (required)
--------------------------------------------------------------------------------
  GET https://api.alpaca.markets/v2/assets
      status      = active
      asset_class = us_equity

  Keep only: tradable == true
             exchange in {NYSE, NASDAQ, AMEX, ARCA, BATS}
             symbol is alphabetic and 5 characters or fewer
  Exclude by name substring (removes funds and structured products):
             ETF, ETN, FUND, TRUST, INDEX, ISHARES, PROSHARES, DIREXION,
             INVESCO, SPDR, VANGUARD, BULL, BEAR, 2X, 3X, ULTRA, LEVERAGED,
             NOTES, PREFERRED, WARRANT, DEPOSITARY, UNIT, ACQUISITION CORP

  Result: approximately 5,033 US common stocks.

KNOWN DEFECT - survivorship bias:
  This endpoint returns only currently-listed symbols. Of the 82 names in the
  original list, 27 no longer appear, which is 33 percent. Those 27 are:
    APE ATNF BBBY BBIG BIGC CARM COMS CRKN EXPR FFIE GREE HOLO HUDI IRNT MARK
    MMAT MULN NKLA PROG RDBX RIDE SAVA SDIG SPRT TRKA TUP WISH
  Every point-in-time result computed on this universe is therefore optimistic,
  because the names that went to zero are absent. This matters more for a
  long-only strategy than for a long-short one. See section 9.1 for the fix.

--------------------------------------------------------------------------------
1.3 SHORT INTEREST (required for the squeeze thesis)
--------------------------------------------------------------------------------
Provider  : FINRA, public CSV, no authentication
Cost      : free
URL       : https://cdn.finra.org/equity/otcmarket/biweekly/shrt<YYYYMMDD>.csv
            where <YYYYMMDD> is a settlement date. Settlement dates fall near
            the 15th and the last business day of each month. Probe plus and
            minus 2 days around each to find the exact published file.
Format    : pipe-delimited
Columns   : symbolCode, currentShortPositionQuantity,
            previousShortPositionQuantity, averageDailyVolumeQuantity,
            daysToCoverQuantity
Coverage  : 2021-01 to present. 131 settlement periods, 522,237 rows,
            5,001 symbols after filtering to common stocks.
Header    : send a browser User-Agent. The default python-requests agent is
            blocked with HTTP 403.

PUBLICATION LAG - mandatory:
  FINRA disseminates roughly 8 business days after the settlement date, which is
  about 12 calendar days. Therefore:
      usable_from = settlement_date + 12 calendar days
  Any code that joins short interest on the settlement date is reading data
  before it was public.

--------------------------------------------------------------------------------
1.4 SOCIAL TEXT (the untested hypothesis, see PART 4)
--------------------------------------------------------------------------------
Provider  : Arctic Shift (Reddit historical archive, Pushshift successor)
Cost      : free, rate limited
Endpoints :
  GET https://arctic-shift.photon-reddit.com/api/comments/search
  GET https://arctic-shift.photon-reddit.com/api/posts/search
      subreddit = wallstreetbets
      after     = <unix epoch, start of day>
      before    = <unix epoch, end of day>
      limit     = 100
Backoff   : on HTTP 422 or 429, sleep 30 seconds and retry, max 5 attempts.
            One full historical pass takes roughly one overnight run.

Live feed for production (no history, cannot backtest):
  GET https://apewisdom.io/api/v1.0/filter/wallstreetbets/page/<n>
      Free, no key. Returns current mention counts and rank change.

BLOCKED - do not attempt:
  reddit.com public JSON returns HTTP 403 for automated agents.
  api.stocktwits.com returns HTTP 403 and 429 intermittently.
  Pushshift is discontinued.

WHAT TO STORE - this is the part the previous version got wrong:
  The previous version stored only a count of ticker mentions per day. A count
  cannot distinguish 100 posts by 100 people from 100 posts by 1 account, cannot
  distinguish a bullish thesis from a warning, and cannot identify whether a
  specific catalyst is named. Store instead, per document:
      doc_id, created_utc, subreddit, author_hash, score (upvotes),
      num_comments, parent_id, body_text (full), and the extracted ticker set.
  Author identity should be hashed, not stored in the clear.

--------------------------------------------------------------------------------
1.5 OPTIONS FLOW (strongest positive signal measured so far)
--------------------------------------------------------------------------------
Provider  : Alpaca OPRA, included in Algo Trader Plus
Coverage  : 2024-01-22 onward. There is no earlier history at this price.
Contracts :
  GET https://api.alpaca.markets/v2/options/contracts
      underlying_symbols = <ticker>
      expiration_date_gte / expiration_date_lte
      strike_price_gte   = 1.10 * spot     (out of the money calls only)
      type               = call
Bars      :
  GET https://data.alpaca.markets/v1beta1/options/bars
      symbols   = OCC contract symbols, batched
      timeframe = 1Day
Derived   : otm_call_volume[s, d] = sum of volume across OTM call contracts

--------------------------------------------------------------------------------
1.6 DATA STILL MISSING - see PART 9 for what each one fixes
--------------------------------------------------------------------------------
  Delisted securities        Polygon or Norgate. Paid. Fixes survivorship.
  Shares outstanding, float  SEC EDGAR 10-Q cover page. Free. Enables market cap.
  Borrow fee, utilisation    Ortex or Fintel. Paid. No free history exists.
  Dilution filings, S-3, ATM SEC EDGAR full-text search. Free.
  Fails to deliver           SEC. Free. 2004 onward. Verified retrievable.


================================================================================
PART 2 - DATA QUALITY GATES
================================================================================
Each gate below exists because a specific defect was found and cost real
analysis time. Run every gate before any modelling. Fail loudly, never silently.

GATE 1 - timestamp alignment
  Symptom found: the price panel carried 05:00:00 timestamps while external
  sources used 00:00:00. The join produced ZERO overlapping days and every
  social feature silently became zero. The conclusion drawn from that run,
  "social data is useless", was an artifact of the join.
  Rule:
      normalise every index to a tz-naive calendar date before joining
      after every join, assert overlap_days > 0.5 * expected_days
      print coverage; do not proceed on zero coverage

GATE 2 - corporate action discontinuity
  Symptom found: GPOR showed a 52,648 percent 20-day gain, AQB showed 367,817
  percent. These are bankruptcy reorganisations where the ticker was reused and
  the adjusted series has a break.
  Rule: drop a symbol-day when any of the following hold
      adv20_usd is null or < 10,000
      atr_pct is null, or <= 0.5 percent, or >= 100 percent
      raw_price < 0.10 or raw_price > 500
      abs(return over 20 days) > 500 percent
  Effect: removes 11 percent of detected events.

GATE 3 - ticker extraction contamination
  Symptom found: uppercasing whole sentences turned "will be" into ticker BE and
  "any" into ANY. 46 percent of all mentions were ordinary English words.
  Rule:
      match only $CASHTAG or a standalone token of 2 to 5 uppercase letters
      maintain a blocklist built from the burst statistic:
          burst[tok] = max(daily_count[tok]) / median(daily_count[tok])
          a real ticker spikes, so burst >= 10; an English word is flat
          block any token with burst < 10 and high absolute frequency
      de-contaminate the remainder by regressing each ticker's daily mentions on
      a pure-English-word proxy series and keeping the residual

GATE 4 - missing-data policy must be explicit
  Symptom found: a short-interest gate returned False when no data existed. That
  silently deleted 2021 through 2024, leaving 84 trades, and the run reported a
  loss of 389 dollars. The bug looked like a strategy result.
  Rule: every gate declares its policy for null input, either "allow" or "block",
  and prints the count of rows affected.

GATE 5 - feature sign must be measured, never assumed
  Symptom found: social mention level was added with a positive weight while its
  measured information coefficient is minus 0.054. The options feature used
  acceleration, whose coefficient is near zero, instead of level, whose
  coefficient is plus 0.061. Correcting the options feature moved expectancy
  from 1.54 percent to 2.10 percent.
  Rule: no feature enters any composite until its information coefficient has
  been measured on a neutral universe, and the weight sign matches that
  measurement.

GATE 6 - solvency
  Symptom found: fixed 10,000 dollar sizing continued after cumulative profit
  reached minus 878,000 dollars on 100,000 dollars of capital. The reported
  maximum drawdown of minus 655 percent is meaningless.
  Rule: halt new entries when equity < one position size. Report dollar profit
  alongside any percentage drawdown.


================================================================================
PART 3 - FEATURE CONSTRUCTION
================================================================================
All features are computed on the split-adjusted series except price level, which
uses the raw series. All are shifted by one session before use.

FUNCTION build_features(day t):

    # --- liquidity and size ---
    adv20_usd   = mean(close[t-20:t] * volume[t-20:t])
    adv20_share = mean(volume[t-20:t])

    # --- volatility ---
    true_range  = max(high - low, |high - prev_close|, |low - prev_close|)
    atr20       = mean(true_range[t-20:t])
    atr_pct     = atr20 / close[t-1]

    # --- trend and position ---
    ma20        = mean(close[t-20:t])
    ma50        = mean(close[t-50:t])
    all_time_hi = max(close[start:t])            # cumulative max, from 2016
    dd_from_ath = close[t-1] / all_time_hi - 1   # ratio, split-invariant
    ret_20d     = close[t-1] / close[t-21] - 1
    ret_60d     = close[t-1] / close[t-61] - 1
    pct_vs_ma20 = close[t-1] / ma20 - 1

    # --- volume behaviour ---
    rvol        = volume[t] / mean(volume[t-20:t])
    vol_build   = mean(volume[t-20:t]) / mean(volume[t-60:t])

    # --- short interest, publication-lagged ---
    si_row      = latest FINRA row where settlement + 12 days <= t
    dtc         = si_row.daysToCoverQuantity
    si_change   = si_row.current / si_row.previous - 1

    # --- price level, RAW series only ---
    price_raw   = raw_close[t-1]

    # --- history ---
    prior_memes = count of completed meme events with peak_date < t
                  (a meme event is a rise of 50 percent or more within 20
                   sessions; it is only KNOWABLE at its peak, so the event
                   becomes usable at peak_date + 1, never at its start)

    # --- social, see PART 4 ---
    soc_level, soc_accel, llm_conviction, llm_coordination, llm_catalyst

    # --- options ---
    otm_call_level = mean(otm_call_volume[t-5:t])   # LEVEL, not acceleration


================================================================================
PART 4 - THE LANGUAGE MODEL LAYER
================================================================================
--------------------------------------------------------------------------------
4.1 WHAT THE MODEL IS AND IS NOT ALLOWED TO DO
--------------------------------------------------------------------------------
ALLOWED   : read social text that already exists and convert it into structured
            numbers. This is a text-processing job.
FORBIDDEN : generate a list of candidate stocks, name tickers from memory, or
            answer any question about what happened after its training cutoff.

  This restriction is the central lesson of the project. The original 82-name
  universe was produced by asking a model to name potential meme stocks. The
  model already knew the answers. That single call invalidated every backtest
  built on top of it. A model may process the past; it must never recall it.

--------------------------------------------------------------------------------
4.2 MODEL SELECTION AND API
--------------------------------------------------------------------------------
Primary, high volume classification of individual documents:
    Model    : claude-haiku-4-5-20251001
    Rationale: millions of short documents, each needing a shallow judgment.
               Cheapest capable model in the current family.

Secondary, daily aggregation and harder judgment:
    Model    : claude-sonnet-5
    Rationale: applied once per ticker per day over an already-summarised
               batch, so volume is roughly 1/1000 of the above. Worth the
               higher cost for coordination and catalyst detection.

API:
    POST https://api.anthropic.com/v1/messages
    Headers:
        x-api-key         : <ANTHROPIC_API_KEY>
        anthropic-version : 2023-06-01
        content-type      : application/json
    Body:
        model, max_tokens, system, messages, temperature = 0

    Use temperature 0. A scoring function must be reproducible; if the same
    input yields different scores on re-run, no backtest is meaningful.

COST CONTROL - both are required at this volume:
    Batch API   : POST https://api.anthropic.com/v1/messages/batches
                  50 percent discount, results within 24 hours. The historical
                  pass is not latency sensitive, so batch everything.
    Prompt cache : mark the system prompt with cache_control ephemeral. The
                  system prompt is identical across millions of calls.

Alternative already available in this project:
    OpenRouter, model deepseek/deepseek-v4-flash
    POST https://openrouter.ai/api/v1/chat/completions
    Cheaper per token. Use it for a first pass to decide whether social data
    carries signal at all, before committing to a full-quality pass.

--------------------------------------------------------------------------------
4.3 COST ESTIMATE, MEASURED FROM ACTUAL VOLUME
--------------------------------------------------------------------------------
    r/wallstreetbets: 10,000 to 80,000 comments per day depending on regime
    2,007 days of history collected  ->  approximately 40 million documents
    Pre-filter to documents containing a ticker  ->  15 to 20 percent remain
                                                 ->  6 to 8 million documents
    At roughly 40 tokens each                    ->  250 to 320 million tokens

    One full historical pass, cheap model, batched : roughly USD 60
    One full historical pass, quality model, batched: roughly USD 800 to 1,000

    Each prompt revision requires a full re-run. Budget for at least three.

VENDOR ALTERNATIVE AND ITS HIDDEN COST:
    Quiver Quantitative, roughly USD 50 to 100 per month, pre-quantified.
    ApeWisdom, free, but shallow history.
    The catch: extraction is exactly where a 46 percent error was found in this
    project (GATE 3). Buying pre-quantified data means inheriting the vendor's
    extraction logic with an unknown and unauditable error rate.
    Recommended sequence: spend roughly USD 100 on vendor data to answer "does
    social carry signal at all", and only build the LLM pipeline if it does.
    Reversing this order spends USD 1,000 to answer a USD 100 question.

--------------------------------------------------------------------------------
4.4 DOCUMENT-LEVEL PROMPT
--------------------------------------------------------------------------------
SYSTEM (cached, identical for every call):
    You are a text classifier for financial social media. You will be given one
    Reddit post or comment. Return only a JSON object, no prose.
    Fields:
      tickers      list of stock tickers the author is actually discussing as
                   investments. Exclude tickers appearing only as ordinary
                   English words. Exclude tickers mentioned only as a comparison.
      stance       one of: bullish, bearish, neutral, unclear
      conviction   integer 0 to 3.
                   0 = passing mention
                   1 = opinion with no support
                   2 = specific reasoning or a price target
                   3 = author states a position they hold, with size or entry
      catalyst     short phrase naming a specific expected event such as
                   "earnings", "FDA decision", "short squeeze", "merger vote",
                   or null if none is named
      is_promotion true when the text reads as coordinated promotion rather than
                   individual opinion: pump language, repeated slogans, an
                   explicit call to buy together
      time_horizon one of: intraday, days, weeks, months, unclear

    You must not use any knowledge of what happened to these stocks after the
    text was written. Judge only what the text itself says.

USER:
    <document body, truncated to 2000 characters>

--------------------------------------------------------------------------------
4.5 DAILY AGGREGATION INTO FEATURES
--------------------------------------------------------------------------------
FUNCTION aggregate_social(ticker s, day d):
    docs = all documents from calendar day d that mention s
           # d is strictly before t. Posts from day t are not available at the
           # close of day t in a reproducible way, so use d = t-1.

    soc_level        = count(docs)
    soc_authors      = count(distinct author_hash in docs)
    soc_accel        = soc_level[d] / mean(soc_level[d-20:d]) - 1
    llm_conviction   = mean(conviction) over docs
    llm_bull_share   = share of docs with stance == bullish
    llm_catalyst     = 1 if any doc names a catalyst, else 0
    llm_promo_share  = share of docs with is_promotion == true

    # coordination: many documents from few authors, or a sudden burst of new
    # accounts, is different from broad organic interest
    concentration    = soc_level / max(soc_authors, 1)

    RETURN all of the above

MEASURED SIGNS - from the existing, admittedly biased, sample:
    soc_level        IC = -0.054   NEGATIVE. Already crowded means late.
    soc_accel        IC = +0.025   weakly positive
    otm_call_level   IC = +0.061   strongest positive found
    dd_from_ath      IC = +0.165   strongest overall, less fallen is better
    prior_memes      IC = -0.152   names that already ran keep falling
    dtc              IC ~  0       no signal at biweekly frequency

  WARNING: every coefficient above was measured on the 195-name pool, which is
  42 percent composed of known meme names against a true base rate near 1
  percent. They are observations, not established properties. All must be
  recomputed on the neutral universe before use. The LLM features have never
  been measured at all.


================================================================================
PART 5 - THE PIPELINE
================================================================================
--------------------------------------------------------------------------------
LAYER 0 - TRADABILITY. Applied identically to every variant, always.
--------------------------------------------------------------------------------
    tradable[s, t] = adv20_usd >= LIQ_FLOOR
                 and adv20_usd <= LIQ_CEIL
                 and raw_price >= 0.20

  This must be applied to the strategy, to the hindsight control, and to the
  random control alike. Failing to do so was a real error: the hindsight run had
  no liquidity filter while the point-in-time run did, which made the comparison
  meaningless and overstated the hindsight advantage by roughly 177,000 dollars.

  CAPACITY WARNING, measured and not fixable with more data:
    Median 20-day dollar volume before a move of 100 percent or more is 861,000
    dollars. Requiring 1 million dollars gives a lift of 0.54x. Requiring 5
    million gives 0.35x. Explosiveness and tradability are opposed. This sets the
    capital ceiling of the entire strategy and no additional data changes it.

--------------------------------------------------------------------------------
LAYER 1 - UNIVERSE. Once per day, before the open. Uses data through t-1 only.
--------------------------------------------------------------------------------
    FOR each symbol s in symbol_master:
        f = build_features(t)
        IF NOT tradable[s, t]: skip

        base_ok = f.atr_pct     >= ATR_FLOOR
              and f.dd_from_ath <= DD_FLOOR
              and f.close       >  f.ma20
              and f.ret_20d     >  RET20_FLOOR

        IF base_ok:
            score[s] = W_ATR  * z(f.atr_pct)
                     + W_DD   * z(-f.dd_from_ath)
                     + W_VB   * z(f.vol_build)
                     + W_SOC  * z(f.soc_accel)        # sign from measurement
                     + W_LVL  * z(-f.soc_level)       # NEGATIVE, measured
                     + W_LLM  * z(f.llm_conviction)   # unmeasured, start at 0
                     + W_OPT  * z(f.otm_call_level)

    universe = top N_UNIVERSE symbols by score

  MEASURED BASE RATES, across 8,967,916 symbol-days, for a gain of 100 percent
  or more within the next 20 sessions:
      no filter                                          0.68 percent
      atr_pct >= 0.12                                    5.52 percent   8.05x
      dd_from_ath <= -0.90                               3.78 percent   5.53x
      ret_20d > 0.20                                     1.94 percent   2.84x
      vol_build >= 1.3                                   1.65 percent   2.40x
      adv20 >= 1e6                                       0.37 percent   0.54x
      adv20 >= 5e6                                       0.24 percent   0.35x
      combined: adv>=1e6, atr>=0.12, above ma20,
                ret20>0.20, dd<=-0.90                    8.35 percent  12.19x
                -> 19,184 symbol-days, about 7.2 names per day

  THE SQUEEZE THESIS DOES NOT SURVIVE MEASUREMENT:
      days_to_cover < 2   lift 1.44x
      days_to_cover >= 3  lift 0.60x
      si_change median before a large move: 0 percent
    Days to cover is inverted relative to the thesis, and short interest change
    carries no signal. Both screens that ranked on days to cover failed for this
    reason. Retain short interest as a diagnostic, not as a ranking weight,
    until borrow fee data exists to test the mechanism properly.

--------------------------------------------------------------------------------
LAYER 2 - IGNITION TRIGGER. Evaluated at the close of day t.
--------------------------------------------------------------------------------
    FOR each s in universe:
        typical = (high[t] + low[t] + close[t]) / 3
        IF  rvol[t]        >= RVOL_MIN     # unusual participation
        AND close[t]       >  typical      # closed in the upper range
        AND close[t]       >  close[t-1]   # rejects a single-day pop
        AND close[t]       >  ma20         # trend filter
        AND ret_5d         >  MOM5_MIN     # rejects sideways drift
        AND pct_vs_ma20    <= EXT_CAP      # not already exhausted
        THEN queue.append((rvol[t], s))

  NOTE ON TIMING, measured: on days that begin a move of 100 percent or more,
  median rvol is 0.97x, meaning volume is NORMAL. Volume rises after the move
  starts, not before. What does precede these moves is vol_build at a median of
  1.28x, a slow accumulation over a month. A trigger keyed to a volume spike is
  therefore structurally late; the accumulation term belongs in Layer 1.

--------------------------------------------------------------------------------
LAYER 2B - INTRADAY CONFIRMATION. Optional. Reduces query volume by design.
--------------------------------------------------------------------------------
    Only symbols that passed Layer 2 are queried intraday, so the 15-minute data
    request covers roughly 10 symbols rather than 5,000.

    FOR each 15-minute bar during the following session:
        slot_rvol = cumulative_volume_at_slot
                    / mean(cumulative_volume_at_same_slot over prior 20 days)
        # time-of-day adjusted: comparing 10:00 volume to a full-day average
        # would flag every stock every morning
        IF slot_rvol >= 2.0 AND price > vwap: confirm and enter
        IF no confirmation by 15:30: stand down, do not enter


================================================================================
PART 6 - EXECUTION AND POSITION MANAGEMENT
================================================================================
    Decision at close[t]. Entry at open[t+1]. NEVER at close[t].
    Measured: entering at the same close used for the decision overstates
    expectancy by 38 percent, from 2.77 percent to 4.48 percent.

    FOR (score, s) in sorted(queue, descending):
        IF open_positions >= MAX_POS: break
        IF equity < POSITION_SIZE: break          # GATE 6
        entry = open[t+1]
        cost  = 2 * min(0.03, 0.0005 + atr_pct * sqrt(POSITION_SIZE / adv20_usd))
        enter(s, entry, POSITION_SIZE)

    EACH SESSION, evaluated in this order:
        stop = entry * (1 - HARD_STOP)
        IF   open[j] <= stop:                 exit at open[j]    # gapped through
        ELIF low[j]  <= stop:                 exit at stop
        ELIF age >= EARLY_DAYS
             AND max_favourable < EARLY_MFE:  exit at close[j]   # no progress
        ELIF close[j] <= peak - ATR_MULT*atr: exit at close[j]   # trailing
        ELIF close[j] > entry
             AND close[j] < ma10:             exit at close[j]   # trend break
        ELIF age >= MAX_HOLD:                 exit at close[j]

  MEASURED EXIT BEHAVIOUR on the original run of 1,167 trades:
      trend break     323 trades  win 100.0 percent  avg +30.4 percent
      trailing stop    20 trades  win  60.0 percent  avg +41.0 percent
      max hold          5 trades  win  40.0 percent  avg  +0.6 percent
      no progress     419 trades  win  20.0 percent  avg  -2.6 percent
      hard stop       400 trades  win   0.0 percent  avg -11.8 percent

  All 10 of the best trades exited on the trend break. All 10 of the worst
  exited on the hard stop, and 7 of those lasted 2 sessions or less, with
  realised losses from 22.8 to 39.1 percent against a nominal stop of 8 percent.
  That difference is overnight gap risk. No stop placement prevents it. The only
  defence is position size.

  ON THE WIN RATE, since it will be asked:
    Every filter that raises the win rate lowers total profit.
        price >= 5 dollars   win 37.2 percent  expectancy +2.77 percent
        adv >= 50 million    win 37.8 percent  expectancy +3.33 percent
        no filter            win 36.1 percent  expectancy +4.12 percent
        rvol >= 5            win 32.7 percent  expectancy +9.32 percent
    Average winner is +30.4 percent, average loser is -11.8 percent, a ratio of
    2.6 to 1, so break-even sits at a win rate of 28 percent. At 36 percent
    there is margin. Win rate is the wrong objective for this payoff shape.

  ON EXIT TIMING: median retracement from the peak within 60 sessions is minus
  55 percent for moves above 100 percent, and minus 67 percent for moves above
  200 percent. Holding through is not viable.


================================================================================
PART 7 - WALK-FORWARD PROTOCOL
================================================================================
This is the part that makes the result trustworthy. Everything above is
mechanics; this section is the experiment.

--------------------------------------------------------------------------------
7.1 WHY THE PREVIOUS VALIDATION FAILED
--------------------------------------------------------------------------------
  A previous walk-forward split the sample into three folds of EQUAL TRADE COUNT
  and all three were positive. Splitting by trade count rather than by calendar
  time concealed that the two most recent years were negative. Folds must be
  defined by date.

  A null test against random entry timing passed at p = 0.025 while the universe
  was invalid, because that test held the universe fixed and only randomised
  entry days. A control must randomise the same thing the strategy chooses. Here
  the strategy chooses names, so the control must choose names randomly.

--------------------------------------------------------------------------------
7.2 SPLIT DEFINITION
--------------------------------------------------------------------------------
    Full sample     : 2016-01-01 to today (price)
    Feature-limited : 2021-01-01 onward (short interest and social both exist)
    Warm-up         : 2016-01-01 to 2020-12-31, used ONLY to establish all-time
                      highs and rolling statistics. No trades, no fitting.

    Rolling folds, all boundaries by calendar date:
        train window = 24 months
        test window  =  6 months
        step         =  6 months
        purge        =  1 month between train end and test start

    The purge gap is required because the label uses a forward 20-session window
    and the maximum hold is 60 sessions. Without it, a trade opened at the end of
    the training window is still open during the test window and the two are not
    independent.

    Folds from 2021-01:
        fold 1  train 2021-01..2022-12  purge 2023-01  test 2023-02..2023-07
        fold 2  train 2021-07..2023-06  purge 2023-07  test 2023-08..2024-01
        fold 3  train 2022-01..2023-12  purge 2024-01  test 2024-02..2024-07
        fold 4  train 2022-07..2024-06  purge 2024-07  test 2024-08..2025-01
        fold 5  train 2023-01..2024-12  purge 2025-01  test 2025-02..2025-07
        fold 6  train 2023-07..2025-06  purge 2025-07  test 2025-08..2026-01
        fold 7  train 2024-01..2025-12  purge 2026-01  test 2026-02..2026-07

--------------------------------------------------------------------------------
7.3 WHAT MAY BE FITTED IN-SAMPLE, AND WHAT MAY NOT
--------------------------------------------------------------------------------
    FITTED on the training window only, re-fitted every fold:
        composite weights W_ATR, W_DD, W_VB, W_SOC, W_LVL, W_LLM, W_OPT
        N_UNIVERSE
        any percentile-based threshold

    FIXED for the whole study, never re-fitted, chosen once and documented:
        RVOL_MIN     2.0     plateau 1.75 to 3.0, Sharpe 0.83 to 0.91
        EXT_CAP      0.50    ablation: 434,670 at none, 519,858 at 0.50, worse
                             at 0.30 and 0.15
        MOM5_MIN     0.05
        HARD_STOP    0.08    ATR is 4 to 8 percent daily, so a tighter stop is
                             hit by ordinary movement. Note: 12 percent tested
                             better, Sharpe 1.18 versus 1.07, but the gap of
                             108,000 dollars is smaller than a single trade
                             (LAES contributed 115,000), so it is inside the
                             noise and 8 percent is retained to avoid fitting.
        EARLY_DAYS   2
        EARLY_MFE    0.03    ablation: +21,491, winners above 50 pct fell 37->35
        ATR_MULT     3.0
        MAX_HOLD     60      winners were held 8 to 37 sessions
        POSITION_SIZE 10,000
        MAX_POS      10
        LIQ_FLOOR    1,000,000
        LIQ_CEIL     300,000,000

    NEVER FITTED, structurally forbidden:
        the symbol list itself. No hand-picked names, ever, from any source
        including a language model.

    LEAKAGE CHECKS to assert inside the fold loop:
        assert every feature timestamp <= fold.test_start for training artifacts
        assert no z-score, percentile, or normalisation constant is computed
               across the full sample
        assert the universe on test day t uses only data through t-1
        assert the FINRA join respects settlement + 12 days
        assert no trade opened in train is still open in test

--------------------------------------------------------------------------------
7.4 CONTROLS - run all three on every fold, identical costs and gates
--------------------------------------------------------------------------------
    STRATEGY  the pipeline above
    FLOOR     N_UNIVERSE symbols drawn at random each day from the same
              tradability-filtered pool, same trigger, same exits
    CEILING   a deliberately biased universe of names known to have run, for
              scale only. Never reported as an achievable result.
    BENCHMARK SPY buy and hold over the identical window

  MEASURED REFERENCE VALUES, same window:
      SPY buy and hold   CAGR +15.9 percent  Sharpe 0.95  maxDD -25.4 percent
      biased 82 names    CAGR +32.7 percent  Sharpe 1.07  maxDD -19.4 percent
      screen v1, valid   CAGR +12.9 percent  Sharpe 0.61  maxDD -36.3 percent
      random control     CAGR  +3.4 percent  Sharpe 0.26
  The only admissible version produced so far, at 0.61, is below SPY at 0.95.
  That is the number to beat.

--------------------------------------------------------------------------------
7.5 ACCEPTANCE CRITERIA - decide these before running, not after
--------------------------------------------------------------------------------
    PASS requires ALL of:
        1. out-of-sample Sharpe > 0.95 in aggregate across folds
           (must beat SPY, not merely beat zero)
        2. at least 5 of 7 folds with positive expectancy
        3. aggregate expectancy exceeds the random floor by at least 2 standard
           errors
        4. removing the top 10 trades leaves aggregate profit positive
        5. beta to SPY below 0.3, preserving the diversification argument
        6. median cost per round trip below one third of gross expectancy

    Criterion 4 is the direct answer to the concentration objection. The thesis
    does depend on large winners, which is legitimate, but a strategy that is
    negative without its ten best trades has no measurable base and cannot be
    distinguished from luck at this sample size.


================================================================================
PART 8 - EVALUATION
================================================================================
    REPORT PER FOLD AND IN AGGREGATE:
        trades, win rate, expectancy, mean cost
        daily mark-to-market equity, then annualised Sharpe, Sortino, Calmar
          (per-trade mean divided by standard deviation is NOT a Sharpe ratio;
           it has no time axis. Cross-check: per_trade_sharpe * sqrt(trades per
           year) should approximate the annualised figure)
        maximum drawdown on the daily curve, and dollar profit alongside it
        exit-reason breakdown
        top 10 and bottom 10 trades with entry date, price, exit, reason
        share of profit from the top 10 trades
        beta, alpha, and correlation against SPY

    ALSO REPORT, because backtests at this sample size cannot settle questions:
        information coefficient per feature, Spearman, cross-sectional, averaged
        by day, on the NEUTRAL universe, at horizons of 5, 10, 20 sessions
        the base rate table of PART 5 recomputed per fold

    Prefer the information coefficient when the two disagree. In one window a
    random control returned plus 8.02 percent per trade and ranked first among
    all variants. A backtest of 300 trades with a heavy right tail cannot
    separate hypotheses; 30,000 cross-sectional observations can.


================================================================================
PART 9 - MISSING DATA, AND THE SPECIFIC GAP EACH ONE CLOSES
================================================================================
Ordered by whether it fixes a known error or tests an open question.

9.1 FIXES A KNOWN ERROR IN NUMBERS ALREADY REPORTED
--------------------------------------------------------------------------------
  RAW UNADJUSTED PRICES
    Gap    : price-level filters currently use split-adjusted prices, which
             embed future corporate actions. 7.8 percent of events affected.
    Source : Alpaca, adjustment=raw. Already paid for.
    Cost   : free, about 30 minutes of fetching
    Fixes  : an active look-ahead leak. Cheapest item on this list.

  DELISTED SECURITIES
    Gap    : the symbol master holds only active listings. 27 of the original 82
             names, 33 percent, are already absent. Every point-in-time result
             is optimistic by an unmeasured amount.
    Source : Polygon or Norgate
    Cost   : USD 30 to 200 per month
    Fixes  : survivorship bias. Critical for a long-only strategy.

  SHARES OUTSTANDING AND FREE FLOAT
    Gap    : market capitalisation is entirely absent. Short interest as a
             percentage of float is being discussed without a denominator.
    Source : SEC EDGAR, 10-Q and 10-K cover page, XBRL facts
             https://data.sec.gov/api/xbrl/companyconcept/CIK<10-digit>/us-gaap/
                 CommonStockSharesOutstanding.json
    Cost   : free, full history
    Fixes  : enables a real size filter and a real float-based short measure.

9.2 TESTS AN OPEN QUESTION
--------------------------------------------------------------------------------
  SOCIAL TEXT ACROSS THE NEUTRAL UNIVERSE
    Gap    : collected for 195 names only, and those 195 are 42 percent known
             meme names. Every social coefficient is therefore measured on a
             contaminated sample and may not generalise.
    Source : Arctic Shift
    Cost   : free, one overnight run per pass
    Tests  : whether attention acceleration selects names before a move.

  SOCIAL DEPTH: AUTHOR IDENTITY AND VOTES
    Gap    : only counts were stored, so coordination cannot be separated from
             one account posting repeatedly.
    Source : same, second pass storing full records
    Tests  : whether coordination, as distinct from volume, is the real signal.
             This is the feature a mention count structurally cannot express,
             and it is the main reason to involve a language model at all.

  OPTIONS ACROSS THE NEUTRAL UNIVERSE
    Gap    : out-of-the-money call level has the strongest positive coefficient
             found, plus 0.061, but was measured on 110 names from the biased
             pool and only from 2024.
    Source : Alpaca OPRA, already accessible
    Cost   : included in the current plan
    Tests  : whether the only surviving positive signal is real.

  BORROW FEE AND UTILISATION
    Gap    : never measured. No coefficient exists because no history exists.
             Every claim about its importance so far rests on the mechanics of a
             squeeze, not on evidence produced here. Given that days to cover
             turned out to be inverted, this assumption deserves scepticism.
    Source : Ortex or Fintel, paid; or start a forward daily record today
    Tests  : whether borrow pressure is the mechanism at all.

9.3 SUPPORTING
--------------------------------------------------------------------------------
  DILUTION FILINGS, S-3 AND AT-THE-MARKET PROGRAMS
    Source : SEC EDGAR full-text search, free
    Tests  : whether dilution explains the median retracement of minus 55
             percent after the peak. If so, it is a strong negative filter.

  FAILS TO DELIVER
    Source : SEC, free, 2004 onward, semi-monthly. Verified retrievable.
    Tests  : settlement stress as an independent squeeze measure.

9.4 WHAT NO DATA CAN FIX
--------------------------------------------------------------------------------
  Median 20-day dollar volume before a move of 100 percent or more is 861,000
  dollars. Liquidity filters reduce the hit rate monotonically: 0.54x at 1
  million dollars, 0.35x at 5 million. The names that explode and the names that
  can absorb capital are nearly disjoint sets. This is a capacity ceiling, not a
  data gap. Establish the intended capital base before spending further on data,
  because at 10,000 dollars per position the strategy is viable and at 100,000
  it may not be.


================================================================================
PART 10 - FAILURE MODES TO WATCH
================================================================================
  1. Any filter tuned until it reproduces a list of known winners. This is
     circular. Coverage of a known list is not a success metric, and treating it
     as one is how the original bias entered.
  2. A robustness test run inside a biased universe. Four of six such tests
     passed on a universe later shown to be invalid.
  3. Percentile thresholds computed over the full sample. Use trailing windows.
  4. A feature whose sign was chosen by intuition. Measure first.
  5. A control that randomises something other than what the strategy chooses.
  6. A "Sharpe ratio" computed across trades with no time axis.
  7. Any prompt that invites the model to recall the past rather than read it.
================================================================================
