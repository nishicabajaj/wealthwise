"""Synthetic data generator: assets, price histories, clients and transactions.

Everything produced here is SYNTHETIC. Prices follow a one-factor market model
(each asset = drift + beta x market + idiosyncratic noise, fat-tailed), so betas,
volatilities and drawdowns behave like real data. To replace them with real
Yahoo Finance history, run scripts/fetch_yahoo.py (needs internet).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

START_DATE = "2023-11-01"
END_DATE = "2026-11-06"
BENCHMARK_START_LEVEL = 19500.0

# symbol, name, class, sector, start price (INR), expected annual return, beta, idiosyncratic annual vol
ASSET_SPECS = [
    ("RELIANCE.NS", "Reliance Industries", "Stock", "Energy", 2300, 0.13, 1.05, 0.22),
    ("TCS.NS", "Tata Consultancy Services", "Stock", "IT", 3450, 0.12, 0.75, 0.20),
    ("HDFCBANK.NS", "HDFC Bank", "Stock", "Financials", 1450, 0.12, 0.95, 0.18),
    ("INFY.NS", "Infosys", "Stock", "IT", 1400, 0.13, 0.85, 0.23),
    ("ICICIBANK.NS", "ICICI Bank", "Stock", "Financials", 940, 0.15, 1.10, 0.19),
    ("ITC.NS", "ITC", "Stock", "FMCG", 430, 0.14, 0.60, 0.18),
    ("LT.NS", "Larsen & Toubro", "Stock", "Industrials", 3000, 0.16, 1.15, 0.20),
    ("HINDUNILVR.NS", "Hindustan Unilever", "Stock", "FMCG", 2450, 0.08, 0.45, 0.17),
    ("SUNPHARMA.NS", "Sun Pharmaceutical", "Stock", "Healthcare", 1150, 0.17, 0.65, 0.22),
    ("MARUTI.NS", "Maruti Suzuki", "Stock", "Auto", 10300, 0.14, 0.95, 0.21),
    ("MF_FLEXI", "WW Flexi Cap Fund", "Mutual Fund", "Diversified Equity", 62.0, 0.14, 0.90, 0.05),
    ("MF_MID", "WW Mid Cap Fund", "Mutual Fund", "Mid Cap Equity", 95.0, 0.17, 1.00, 0.08),
    ("MF_LARGE", "WW Bluechip Fund", "Mutual Fund", "Large Cap Equity", 78.0, 0.12, 0.95, 0.03),
    ("MF_BAL", "WW Balanced Advantage Fund", "Mutual Fund", "Hybrid", 41.0, 0.10, 0.50, 0.02),
    ("MF_LIQ", "WW Liquid Fund", "Mutual Fund", "Debt", 1250.0, 0.065, 0.0, 0.003),
    ("NIFTYBEES.NS", "Nippon India Nifty 50 BeES", "ETF", "Index", 215, 0.125, 1.00, 0.01),
    ("GOLDBEES.NS", "Nippon India Gold BeES", "ETF", "Gold", 52, 0.12, -0.05, 0.13),
    ("BANKBEES.NS", "Nippon India Bank BeES", "ETF", "Banking", 450, 0.12, 1.05, 0.08),
    ("GSEC_2034", "GoI 7.10% G-Sec 2034", "Bond", "Government", 100, 0.07, -0.05, 0.03),
    ("CORP_AAA_2029", "AAA Corporate Bond 2029", "Bond", "Corporate", 100, 0.0775, 0.03, 0.025),
    ("SDL_2033", "State Development Loan 2033", "Bond", "Government", 100, 0.0725, -0.03, 0.03),
]

FIRST = ["Aarav", "Vivaan", "Aditya", "Ananya", "Diya", "Ishaan", "Kavya", "Rohan", "Priya",
         "Arjun", "Neha", "Siddharth", "Meera", "Karan", "Sneha", "Rahul", "Pooja", "Vikram",
         "Anjali", "Rajesh", "Sunita", "Amit", "Deepa", "Manish", "Lakshmi"]
LAST = ["Sharma", "Patel", "Iyer", "Reddy", "Nair", "Gupta", "Mehta", "Joshi", "Kulkarni",
        "Banerjee", "Singh", "Desai", "Menon", "Chopra", "Bhatt", "Rao", "Verma", "Shah",
        "Pillai", "Kapoor", "Agarwal", "Naik", "Deshmukh", "Chatterjee", "Malhotra"]
CITIES = ["Mumbai", "Pune", "Thane", "Bengaluru", "Delhi", "Chennai", "Hyderabad", "Ahmedabad", "Kolkata"]
JOBS = ["Software Engineer", "Doctor", "Business Owner", "Chartered Accountant", "Teacher",
        "Government Officer", "Consultant", "Architect", "Marketing Manager", "Retired"]
OBJECTIVES = {
    "Low": ["Capital Preservation", "Regular Income", "Retirement"],
    "Medium": ["Retirement", "Child Education", "Home Purchase", "Wealth Creation"],
    "High": ["Wealth Creation", "Aggressive Growth", "Early Retirement"],
}
HORIZON = {"Low": (3, 8), "Medium": (5, 12), "High": (8, 20)}


# --------------------------------------------------------------------------
def generate_assets() -> pd.DataFrame:
    rows = []
    for i, (sym, name, cls, sector, *_rest) in enumerate(ASSET_SPECS, start=1):
        rows.append(dict(asset_id=f"A{i:03d}", symbol=sym, asset_name=name, asset_class=cls,
                         sector=sector, currency="INR", data_source="synthetic"))
    return pd.DataFrame(rows)


def generate_prices(assets: pd.DataFrame, rng: np.random.Generator):
    """Return (wide prices DataFrame, benchmark Series) on business days."""
    dates = pd.bdate_range(START_DATE, END_DATE)
    n = len(dates)
    mkt_mu, mkt_vol = 0.12, 0.14

    def shocks(size):  # fat-tailed (Student-t, df=5) scaled to unit variance
        return rng.standard_t(5, size) / np.sqrt(5 / 3)

    m = mkt_mu / 252 + mkt_vol / np.sqrt(252) * shocks(n)
    c0 = int(n * 0.55)                       # one market correction + partial recovery
    m[c0:c0 + 25] -= 0.0045
    m[c0 + 25:c0 + 65] += 0.0015

    bench = pd.Series(BENCHMARK_START_LEVEL * np.cumprod(1 + m), index=dates).round(2)
    out = {}
    for spec, aid in zip(ASSET_SPECS, assets["asset_id"]):
        _, _, _, _, p0, mu, beta, idio = spec
        r = mu / 252 + beta * (m - mkt_mu / 252) + idio / np.sqrt(252) * shocks(n)
        out[aid] = np.round(p0 * np.cumprod(1 + r), 2)
    return pd.DataFrame(out, index=dates), bench


def generate_clients(rng: np.random.Generator, n: int = 25) -> pd.DataFrame:
    risks = rng.choice(config.RISK_LEVELS, size=n, p=[0.32, 0.44, 0.24])
    last = rng.permutation(LAST)[:n]
    join_pool = pd.bdate_range(START_DATE, "2025-03-31")
    rows = []
    for i in range(n):
        risk = str(risks[i])
        lo, hi = HORIZON[risk]
        income = float(np.round(np.exp(rng.normal(np.log(1_400_000), 0.55)), -3))
        age = int(rng.integers(28, 66))
        first, ln = FIRST[i], str(last[i])
        rows.append(dict(
            client_id=f"C{i + 1:03d}", full_name=f"{first} {ln}",
            email=f"{first.lower()}.{ln.lower()}@example.com",
            phone=f"+91-9{int(rng.integers(0, 10**9)):09d}",
            city=str(rng.choice(CITIES)),
            date_of_birth=(pd.Timestamp(END_DATE) - pd.Timedelta(days=int(age * 365.25 + rng.integers(0, 300)))).strftime("%Y-%m-%d"),
            occupation=str(rng.choice(JOBS)), annual_income=max(income, 300_000.0),
            risk_appetite=risk, investment_objective=str(rng.choice(OBJECTIVES[risk])),
            investment_horizon_years=int(rng.integers(lo, hi + 1)),
            join_date=join_pool[int(rng.integers(0, len(join_pool)))].strftime("%Y-%m-%d"),
        ))
    return pd.DataFrame(rows)


def generate_transactions(clients, assets, prices, rng) -> pd.DataFrame:
    idx = prices.index
    classes = config.ASSET_CLASSES
    by_class = {c: assets.loc[assets.asset_class == c, "asset_id"].tolist() for c in classes}
    cls_of = assets.set_index("asset_id")["asset_class"]
    n_pick = {"Stock": (2, 5), "Mutual Fund": (1, 3), "ETF": (1, 2), "Bond": (1, 2)}
    rows: list[dict] = []

    def trading_day(d):
        pos = idx.searchsorted(pd.Timestamp(d))
        return idx[pos] if pos < len(idx) else None

    def held(cid, aid, upto):
        q = 0.0
        for r in rows:
            if r["client_id"] == cid and r["asset_id"] == aid and r["txn_date"] <= upto:
                q += r["quantity"] if r["txn_type"] == "BUY" else -r["quantity"]
        return q

    def buy(cid, aid, day, amount, note):
        if day is None:
            return
        px = float(prices.at[day, aid])
        qty = float(np.floor(amount / px)) if cls_of[aid] == "Stock" else round(amount / px, 3)
        if qty > 0:
            rows.append(dict(client_id=cid, asset_id=aid, txn_date=day, txn_type="BUY",
                             quantity=qty, price=px, notes=note))

    for c in clients.itertuples():
        cid, join = c.client_id, pd.Timestamp(c.join_date)
        tgt = config.TARGET_ALLOCATION[c.risk_appetite]
        w = np.array([tgt[k] * rng.uniform(0.55, 1.45) for k in classes])
        w = w / w.sum()
        lump = float(np.clip(c.annual_income * rng.uniform(0.4, 1.2), 100_000, 1_500_000))

        picks = {}
        for k in classes:
            lo, hi = n_pick[k]
            m = int(rng.integers(lo, hi + 1))
            picks[k] = list(rng.choice(by_class[k], size=min(m, len(by_class[k])), replace=False))
        for k, wk in zip(classes, w):
            split = rng.dirichlet(np.ones(len(picks[k])))
            for aid, s in zip(picks[k], split):
                buy(cid, aid, trading_day(join + pd.Timedelta(days=int(rng.integers(0, 7)))),
                    lump * wk * s, "Initial investment")

        fund_like = picks["Mutual Fund"] + picks["ETF"]
        if rng.random() < 0.6 and fund_like:                    # monthly SIP
            sip = float(np.round(rng.uniform(5_000, 25_000) / 500) * 500)
            sip_assets = list(rng.choice(fund_like, size=min(len(fund_like), int(rng.integers(1, 3))), replace=False))
            d = (join + pd.DateOffset(months=1)).replace(day=5)
            while d <= idx[-1]:
                for aid in sip_assets:
                    buy(cid, aid, trading_day(d), sip / len(sip_assets), "SIP")
                d = d + pd.DateOffset(months=1)

        all_assets = [a for k in classes for a in picks[k]]
        for _ in range(int(rng.integers(0, 4))):                 # top-ups
            lo_d, hi_d = join + pd.Timedelta(days=60), idx[-1] - pd.Timedelta(days=10)
            if lo_d < hi_d:
                d = lo_d + pd.Timedelta(days=int(rng.integers(0, (hi_d - lo_d).days)))
                buy(cid, str(rng.choice(all_assets)), trading_day(d), lump * rng.uniform(0.05, 0.3), "Top-up")

        for _ in range(int(rng.integers(0, 3))):                 # partial sells
            lo_d, hi_d = join + pd.Timedelta(days=120), idx[-1] - pd.Timedelta(days=5)
            if lo_d >= hi_d:
                continue
            d = trading_day(lo_d + pd.Timedelta(days=int(rng.integers(0, (hi_d - lo_d).days))))
            aid = str(rng.choice(all_assets))
            q = held(cid, aid, d) * rng.uniform(0.1, 0.4)
            q = float(np.floor(q)) if cls_of[aid] == "Stock" else round(q, 3)
            if q > 0:
                rows.append(dict(client_id=cid, asset_id=aid, txn_date=d, txn_type="SELL",
                                 quantity=q, price=float(prices.at[d, aid]), notes="Partial redemption"))

    t = pd.DataFrame(rows).sort_values(["txn_date", "client_id", "asset_id"]).reset_index(drop=True)
    t.insert(0, "txn_id", np.arange(1, len(t) + 1))
    return t


def generate_all(seed: int = 42) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    assets = generate_assets()
    prices_wide, bench = generate_prices(assets, rng)
    clients = generate_clients(rng)
    txns = generate_transactions(clients, assets, prices_wide, rng)
    prices_long = (prices_wide.rename_axis("price_date").reset_index()
                   .melt(id_vars="price_date", var_name="asset_id", value_name="close_price"))
    bench_long = pd.DataFrame({"benchmark_code": config.BENCHMARK_CODE,
                               "price_date": bench.index, "close_value": bench.values})
    return dict(clients=clients, assets=assets, prices=prices_long,
                benchmark_prices=bench_long, transactions=txns)
