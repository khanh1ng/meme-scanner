# ARCHIVE — superseded by scripts/ and src/memescan/. Credentials removed.
#!/usr/bin/env python3
"""So sanh TAT CA cac phien ban chon universe. Chay sau khi fetch Reddit xong.
   Dung: python3 compare_versions.py
   Moi feature deu shift(1) / tru do tre cong bo -> KHONG look-ahead."""
import pandas as pd, numpy as np, sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
from collections import defaultdict

C = Path("meme_cache"); ALLOC, CAP, MAXPOS = 10000.0, 100000.0, 10
def load(p):
    p = Path(p)
    if p.exists():
        try: return pd.read_parquet(p)
        except Exception: pass
    pk = Path(str(p) + ".pkl")
    return pd.read_pickle(pk) if pk.exists() else None

pool = load(C / "pool_universe.parquet")
if pool is None: sys.exit("Thieu pool_universe.parquet")
pool = pool.sort_values(["ticker", "date"])
memeset = set(load(C / "bt_daily.parquet")["ticker"].unique())

cl = pool.pivot(index="date", columns="ticker", values="close")
vo = pool.pivot(index="date", columns="ticker", values="vol")
hi = pool.pivot(index="date", columns="ticker", values="high")
lo = pool.pivot(index="date", columns="ticker", values="low")
op = pool.pivot(index="date", columns="ticker", values="open")
dv = cl * vo
DATES = list(cl.index); TICKS = list(cl.columns)
print(f"Pool: {len(TICKS)} ma | {len(DATES)} ngay | {DATES[0].date()} -> {DATES[-1].date()}")


def align_daily(df_wide, target_index):
    """Khop theo NGAY LICH: pool co timestamp 05:00, mentions/options co 00:00.
       Neu reindex truc tiep se ra 0 ngay giao nhau -> social/options bi zero am tham."""
    d = df_wide.copy()
    d.index = pd.DatetimeIndex(d.index).normalize()
    d = d[~d.index.duplicated(keep="last")]
    out = d.reindex(pd.DatetimeIndex(target_index).normalize())
    out.index = target_index
    return out

zs = lambda d: d.sub(d.mean(axis=1), axis=0).div(d.std(axis=1).replace(0, np.nan), axis=0)

# ---------- A. Feature GIA/VOLUME (shift 1) ----------
dv_s, cl_s, hi_s, lo_s = dv.shift(1), cl.shift(1), hi.shift(1), lo.shift(1)
tr_ = pd.concat([hi_s - lo_s, (hi_s - cl_s.shift(1)).abs(), (lo_s - cl_s.shift(1)).abs()]).groupby(level=0).max()
BASE = (zs(dv_s.rolling(5).mean() / dv_s.rolling(60).mean()).fillna(0)
        + zs((tr_.rolling(5).mean() / cl_s) / (tr_.rolling(60).mean() / cl_s)).fillna(0)
        + .5 * zs(cl_s / cl_s.shift(20) - 1).fillna(0)
        + .5 * zs(-np.log(cl_s.clip(lower=.01))).fillna(0))
LIQ = dv_s.rolling(20).mean() >= 1e6

# ---------- B. SHORT INTEREST (FINRA, tru 8 ngay cong bo) ----------
SI_CHG = pd.DataFrame(0.0, index=DATES, columns=TICKS)
SI_DTC = pd.DataFrame(0.0, index=DATES, columns=TICKS)
si = load(C / "finra_si_history.parquet")
if si is not None and len(si):
    si = si.sort_values(["ticker", "settle"]).copy()
    # FINRA cong bo ~8 NGAY LAM VIEC sau settlement = ~12 ngay lich. Dung 12 cho AN TOAN
    si["pub"] = si["settle"] + pd.Timedelta(days=12)
    si["chg"] = si.groupby("ticker")["short_int"].pct_change()
    dnp = np.array(DATES, dtype="datetime64[ns]")
    for tk, g in si.groupby("ticker"):
        if tk not in SI_CHG.columns: continue
        g = g.dropna(subset=["pub"]).sort_values("pub")
        idx = np.searchsorted(g["pub"].values.astype("datetime64[ns]"), dnp, side="right") - 1
        ok = idx >= 0
        if ok.any():
            SI_CHG.loc[ok, tk] = np.nan_to_num(g["chg"].values[idx[ok]])
            if "dtc" in g: SI_DTC.loc[ok, tk] = np.nan_to_num(g["dtc"].values[idx[ok]])
    print(f"FINRA SI: {si.ticker.nunique()} ma | {si.settle.min().date()} -> {si.settle.max().date()}")
else:
    print("FINRA SI: khong co -> phien ban SI se giong ban gia/volume")

# ---------- C. SOCIAL (Reddit, mention ngay d chi dung tu ngay d+1) ----------
SOC_Z = pd.DataFrame(0.0, index=DATES, columns=TICKS)
SOC_AC = pd.DataFrame(0.0, index=DATES, columns=TICKS)
HAS_SOC = False
rm = load(C / "reddit_mentions.parquet")
if rm is not None and len(rm):
    rm = rm[rm["ticker"].isin(TICKS)].copy()
    if len(rm):
        M = align_daily(rm.pivot_table(index="date", columns="ticker", values="mentions",
                                       aggfunc="sum"), DATES).reindex(columns=TICKS)
        cover = M.notna().any(axis=1); M = M.fillna(0.0)

        # --- LAM SACH EXTRACTOR (bug: .upper() khien tu tieng Anh thanh ticker) ---
        try:    words = {w.strip().upper() for w in open("/usr/share/dict/words") if 2 <= len(w.strip()) <= 5}
        except Exception: words = set()
        burst = {t: (M[t].max()/max(M[t][M[t] > 0].median(), 1)) if (M[t] > 0).any() else 0 for t in M.columns}
        pctd  = {t: (M[t] > 0).mean() for t in M.columns}
        BLOCK = [t for t in M.columns if t in words and burst[t] < 10 and pctd[t] > 0.6]
        PROXY = [t for t in ("BE", "ANY", "HE") if t in M.columns]
        proxy = M[PROXY].sum(axis=1) if PROXY else pd.Series(0.0, index=M.index)
        M[BLOCK] = 0.0                                   # bo han ma bi nhiem nang
        n_fix = 0
        if proxy.std() > 0:                              # khu nhiem phan du cho ma trong tu dien
            for t in M.columns:
                if t in words and t not in BLOCK:
                    b = np.polyfit(proxy, M[t], 1)[0]
                    if b > 0: M[t] = (M[t] - b*proxy).clip(lower=0); n_fix += 1
        print(f"Reddit lam sach: chan {len(BLOCK)} ma ({', '.join(BLOCK) if BLOCK else '-'}), "
              f"khu nhiem {n_fix} ma trong tu dien")

        Ms = np.log1p(M).shift(1)                       # <-- tre 1 ngay: khong look-ahead
        # IC do duoc (2021-2023, ~657 ngay): accel20 = +0.025 | level = -0.064 (NGUOC DAU)
        # -> level phai vao voi dau AM (tranh ten da dong), khong phai dau duong nhu ban dau.
        SOC_Z  = zs(Ms.rolling(20, min_periods=3).mean()).fillna(0)          # level, IC AM
        SOC_AC = zs(Ms - Ms.rolling(20, min_periods=5).mean()).fillna(0)     # accel20, IC DUONG
        HAS_SOC = True
        print(f"Reddit: {rm.ticker.nunique()} ma | {int(cover.sum())}/{len(DATES)} ngay co du lieu "
              f"({cover.sum()/len(DATES):.1%} phu song)")
        if cover.sum() == 0:
            print("  !!! CANH BAO: 0 ngay khop - kiem tra lech timestamp truoc khi tin ket qua")
            HAS_SOC = False
if not HAS_SOC:
    print("Reddit: chua co du lieu -> phien ban social se bi BO QUA")

# ---------- D. OPTIONS FLOW (OTM call volume surge, Alpaca OPRA tu 2024-01-22) ----------
OPT = pd.DataFrame(0.0, index=DATES, columns=TICKS)
HAS_OPT = False
of = load(C / "options_flow.parquet")
if of is not None and len(of):
    of = of[of["ticker"].isin(TICKS)]
    if len(of):
        O = align_daily(of.pivot_table(index="date", columns="ticker", values="otm_call_vol",
                                       aggfunc="sum"), DATES).reindex(columns=TICKS).fillna(0.0)
        Os = np.log1p(O).shift(1)                      # <-- tre 1 ngay
        # IC: OTM call LEVEL = +0.061 (manh nhat) | accel20 = +0.005 -> dung LEVEL
        OPT = zs(Os.rolling(20, min_periods=5).mean()).fillna(0)
        HAS_OPT = True
        cov = (O > 0).any(axis=1)
        print(f"Options flow: {of.ticker.nunique()} ma | {int(cov.sum())}/{len(DATES)} ngay "
              f"({cov.sum()/len(DATES):.1%} phu song, chi tu 2024)")
if not HAS_OPT:
    print("Options flow: chua co du lieu -> phien ban options se bi BO QUA")

SC = {"base": BASE,
      "si":   BASE + 1.5 * zs(SI_CHG).fillna(0) + 1.0 * zs(SI_DTC).fillna(0),
      "soc":  BASE + 1.5 * SOC_AC - 1.0 * SOC_Z,   # dau AM cho level
      "all":  BASE + 1.0 * zs(SI_CHG).fillna(0) + 1.5 * SOC_AC - 1.0 * SOC_Z,
      "opt":  BASE + 1.5 * OPT,
      "max":  BASE + 1.0 * zs(SI_CHG).fillna(0) + 1.5 * SOC_AC - 1.0 * SOC_Z + 1.0 * OPT}
RANK = {k: v.where(LIQ).rank(axis=1, ascending=False) for k, v in SC.items()}

def atr14(h, l, c, w=14):
    n = len(c); t = np.zeros(n)
    for i in range(1, n): t[i] = max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1]))
    a = np.full(n, np.nan)
    for i in range(w, n): a[i] = t[i-w+1:i+1].mean()
    return a

def backtest(member):
    tr = []
    for sym in TICKS:
        c = cl[sym].values; v = vo[sym].values; h = hi[sym].values
        l = lo[sym].values; o = op[sym].values
        if (~np.isnan(c)).sum() < 200: continue
        atr = atr14(np.nan_to_num(h), np.nan_to_num(l), np.nan_to_num(c)); n = len(c); i = 21
        while i < n - 2:
            if np.isnan(c[i]) or np.isnan(o[i+1]): i += 1; continue
            base = np.nanmean(v[i-20:i]); rv = v[i]/base if base > 0 else 0
            ma = np.nanmean(c[i-20:i]); ext = c[i]/ma - 1 if ma > 0 else 0
            typ = (h[i]+l[i]+c[i])/3
            if (rv >= 2.0 and c[i] > typ and c[i] > c[i-1] and ext <= .5 and c[i] > ma
                    and c[i]/c[i-5]-1 > .05 and member(DATES[i], sym)):
                ei = i+1; e = o[i+1]
                if e <= 0: i += 1; continue
                peak = e; xi = min(ei+60, n-1); ex = None
                for j in range(ei+1, xi+1):
                    if np.isnan(c[j]): continue
                    sp = e*.92
                    if o[j] <= sp: xi, ex = j, o[j]; break
                    if l[j] <= sp: xi, ex = j, sp; break
                    if (j-ei) >= 2 and (np.nanmax(c[ei+1:j+1])/e - 1) < .03: xi, ex = j, c[j]; break
                    peak = max(peak, c[j])
                    if c[j] <= peak - 3*(atr[j] if not np.isnan(atr[j]) else 0): xi, ex = j, c[j]; break
                    if c[j] > e and c[j] < np.nanmean(c[max(0, j-9):j+1]): xi, ex = j, c[j]; break
                if ex is None or np.isnan(ex): ex = c[xi]
                tr.append({"ticker": sym, "ei": ei, "xi": xi, "entry_date": DATES[ei],
                           "exit_date": DATES[xi], "entry_px": e, "ret": ex/e - 1})
                i = xi+1; continue
            i += 1
    td = pd.DataFrame(tr)
    if len(td) == 0: return None
    td = td.sort_values("entry_date").reset_index(drop=True)
    rows, opens = [], []
    for _, t in td.iterrows():
        opens = [d for d in opens if d > t["entry_date"]]
        if len(opens) >= MAXPOS: continue
        opens.append(t["exit_date"]); rows.append({**t.to_dict(), "pnl": ALLOC*t["ret"]})
    tk = pd.DataFrame(rows)
    acc = defaultdict(float)
    for _, t in tk.iterrows():
        c = cl[t["ticker"]].values; sh = ALLOC/t["entry_px"]
        for j in range(int(t["ei"])+1, int(t["xi"])+1):
            if not np.isnan(c[j]) and not np.isnan(c[j-1]): acc[DATES[j]] += sh*(c[j]-c[j-1])
    eq = CAP + pd.Series([acc.get(d, 0.) for d in DATES], index=DATES).cumsum()
    r = eq.pct_change().dropna(); yrs = (DATES[-1]-DATES[0]).days/365.25
    dn = r[r < 0]
    return dict(n=len(tk), win=(tk.ret > 0).mean(), exp=tk.ret.mean(),
                cagr=(eq.iloc[-1]/CAP)**(1/yrs)-1,
                sharpe=r.mean()/r.std()*np.sqrt(252) if r.std() > 0 else np.nan,
                sortino=r.mean()/dn.std()*np.sqrt(252) if len(dn) and dn.std() > 0 else np.nan,
                dd=((eq-eq.cummax())/eq.cummax()).min(), final=eq.iloc[-1])

def topk(key, k):
    R = RANK[key]
    def f(d, s):
        v = R.at[d, s]
        return (not np.isnan(v)) and v <= k
    return f

rng = np.random.default_rng(1)
RS = {d: set(rng.choice(TICKS, size=min(30, len(TICKS)), replace=False)) for d in DATES}

TESTS = [("1. HINDSIGHT seed 82 (BIAS - doi chieu)", lambda d, s: s in memeset),
         ("2. PIT gia/volume TOP-30",                topk("base", 30)),
         ("3. PIT + short-interest FINRA TOP-30",    topk("si", 30))]
if HAS_SOC:
    TESTS += [("4. PIT + SOCIAL Reddit TOP-30",      topk("soc", 30)),
              ("5. PIT + SOCIAL + SI TOP-30",        topk("all", 30))]
if HAS_OPT:
    TESTS += [("6. PIT + OPTIONS flow TOP-30",       topk("opt", 30))]
if HAS_SOC and HAS_OPT:
    TESTS += [("7. PIT + SOCIAL + SI + OPTIONS",     topk("max", 30))]
TESTS += [("8. Ngau nhien 30/ngay (control)",        lambda d, s: s in RS[d])]

print("\n" + "="*112)
print("SO SANH TAT CA PHIEN BAN  (khong look-ahead: feature shift(1), FINRA -8 ngay, Reddit -1 ngay)")
print("="*112)
print(f"{'':40s} {'n':>5s} {'win':>7s} {'exp':>8s} {'CAGR':>8s} {'Sharpe':>7s} {'Sortino':>8s} {'maxDD':>8s} {'final':>11s}")
res = {}
for lbl, fn in TESTS:
    m = backtest(fn)
    res[lbl] = m
    if m is None: print(f"{lbl:40s} 0 trades"); continue
    print(f"{lbl:40s} {m['n']:5d} {m['win']:7.1%} {m['exp']:+8.2%} {m['cagr']:8.1%} "
          f"{m['sharpe']:7.2f} {m['sortino']:8.2f} {m['dd']:8.1%} {m['final']:11,.0f}")

print("""
DOC KET QUA:
  - So (2) voi (6): selector point-in-time co skill that khong.
  - So (4)/(5) voi (2): SOCIAL co them gia tri ngoai gia/volume khong  <-- cau hoi chinh.
  - (1) chi de doi chieu: phan cao hon (2) chinh la muc do ao do chon ten bang hindsight.""")
pd.DataFrame({k: v for k, v in res.items() if v}).T.to_csv(C / "version_comparison.csv")
print("Saved:", C / "version_comparison.csv")
