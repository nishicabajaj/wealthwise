"""Financial modelling engine (Modules 2 and 3): holdings, valuation, KPIs.

Cost-basis convention (also used by the SQL views):
    average cost = total BUY cost / total units bought
    realised P&L = sell proceeds - units sold x average cost
Portfolio return series are time-weighted: each day's return uses the previous
day's positions, so deposits and withdrawals never distort performance.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, risk
from .store import Dataset

EPS = 1e-6


# ---- Holdings & valuation ---------------------------------------------------
def compute_holdings(ds: Dataset, client_id: str | None = None, include_closed: bool = False) -> pd.DataFrame:
    t = ds.transactions
    if client_id is not None:
        t = t[t["client_id"] == client_id]
    cols = ["client_id", "asset_id", "symbol", "asset_name", "asset_class", "sector", "quantity",
            "avg_cost", "invested", "current_price", "market_value", "unrealized_pnl", "roi_pct",
            "realized_pnl", "weight"]
    if t.empty:
        return pd.DataFrame(columns=cols)
    buy = t["txn_type"].eq("BUY")
    f = pd.DataFrame({
        "client_id": t["client_id"], "asset_id": t["asset_id"],
        "buy_qty": t["quantity"].where(buy, 0.0), "buy_cost": (t["quantity"] * t["price"]).where(buy, 0.0),
        "sell_qty": t["quantity"].where(~buy, 0.0), "sell_proceeds": (t["quantity"] * t["price"]).where(~buy, 0.0),
    })
    g = f.groupby(["client_id", "asset_id"], as_index=False).sum()
    g["quantity"] = g["buy_qty"] - g["sell_qty"]
    g["avg_cost"] = g["buy_cost"] / g["buy_qty"].replace(0, np.nan)
    g["realized_pnl"] = g["sell_proceeds"] - g["sell_qty"] * g["avg_cost"]
    if not include_closed:
        g = g[g["quantity"] > EPS]
    g = g.merge(ds.assets[["asset_id", "symbol", "asset_name", "asset_class", "sector"]], on="asset_id")
    g["current_price"] = g["asset_id"].map(ds.latest_prices)
    g["invested"] = g["quantity"] * g["avg_cost"]
    g["market_value"] = g["quantity"] * g["current_price"]
    g["unrealized_pnl"] = g["market_value"] - g["invested"]
    g["roi_pct"] = np.where(g["invested"] > 0, g["unrealized_pnl"] / g["invested"] * 100, np.nan)
    tot = g.groupby("client_id")["market_value"].transform("sum")
    g["weight"] = np.where(tot > 0, g["market_value"] / tot, 0.0)
    return g[cols].reset_index(drop=True)


def position_matrix(ds: Dataset, client_ids=None):
    """Units held at each trading day close (dates x assets) and daily net cash flow."""
    idx, cols = ds.prices.index, ds.prices.columns
    t = ds.transactions
    if client_ids is not None:
        t = t[t["client_id"].isin(list(client_ids))]
    pos = idx.searchsorted(t["txn_date"])
    keep = pos < len(idx)
    t, pos = t[keep], pos[keep]
    sign = np.where(t["txn_type"].eq("BUY"), 1.0, -1.0)
    d = pd.DataFrame({"day": idx[pos], "asset_id": t["asset_id"].values,
                      "dq": sign * t["quantity"].values, "cash": sign * (t["quantity"] * t["price"]).values})
    if d.empty:
        return pd.DataFrame(0.0, index=idx, columns=cols), pd.Series(0.0, index=idx)
    dq = d.pivot_table(index="day", columns="asset_id", values="dq", aggfunc="sum")
    dq = dq.reindex(index=idx, columns=cols).fillna(0.0)
    flows = d.groupby("day")["cash"].sum().reindex(idx).fillna(0.0)
    return dq.cumsum(), flows


def portfolio_series(prices: pd.DataFrame, positions: pd.DataFrame, flows: pd.Series | None = None) -> pd.DataFrame:
    """Daily value, time-weighted return, wealth index (=100 at start), cumulative P&L."""
    value = (positions * prices).sum(axis=1)
    if not (value > 0).any():
        return pd.DataFrame(columns=["value", "net_invested", "pnl", "ret", "wealth", "drawdown"])
    pnl_day = (positions.shift(1).fillna(0.0) * prices.diff()).sum(axis=1)
    prev = value.shift(1)
    ret = (pnl_day / prev).where(prev > 0, 0.0)
    out = pd.DataFrame({"value": value, "ret": ret})
    out["net_invested"] = (flows if flows is not None else pd.Series(0.0, index=value.index)).cumsum()
    out["pnl"] = out["value"] - out["net_invested"]
    out = out.loc[value[value > 0].index[0]:].copy()
    out["ret"] = out["ret"].fillna(0.0)
    out.iloc[0, out.columns.get_loc("ret")] = 0.0
    out["wealth"] = 100.0 * (1 + out["ret"]).cumprod()
    out["drawdown"] = risk.drawdown_series(out["wealth"])
    return out[["value", "net_invested", "pnl", "ret", "wealth", "drawdown"]]


def client_series(ds: Dataset, client_id: str | None = None) -> pd.DataFrame:
    """Series for one client, or for the whole firm when client_id is None."""
    pos, flows = position_matrix(ds, None if client_id is None else [client_id])
    return portfolio_series(ds.prices, pos, flows)


def static_backtest(ds: Dataset, client_id: str, freq: str = "ME") -> pd.DataFrame:
    """Back-test TODAY's holdings over history (month-end). Mirrors the Excel model."""
    h = compute_holdings(ds, client_id)
    q = h.set_index("asset_id")["quantity"].reindex(ds.prices.columns).fillna(0.0)
    val = (ds.prices * q).sum(axis=1).resample(freq).last()
    bench = ds.benchmark.resample(freq).last()
    return pd.DataFrame({"value": val, "ret": val.pct_change(), "bench": bench, "bench_ret": bench.pct_change()})


# ---- KPIs --------------------------------------------------------------------
def asset_performance(h: pd.DataFrame) -> pd.DataFrame:
    a = (h.groupby(["asset_id", "symbol", "asset_name", "asset_class"], as_index=False)
         [["invested", "market_value", "unrealized_pnl"]].sum())
    a["roi_pct"] = a["unrealized_pnl"] / a["invested"] * 100
    return a.sort_values("roi_pct", ascending=False).reset_index(drop=True)


def firm_kpis(ds: Dataset) -> dict:
    h = compute_holdings(ds)
    closed = compute_holdings(ds, include_closed=True)
    invested, value = float(h["invested"].sum()), float(h["market_value"].sum())
    fs = client_series(ds)
    m = risk.analyze_series(fs, ds.benchmark)
    perf = asset_performance(h)
    best = perf.iloc[0] if len(perf) else None
    return dict(
        total_aum=value, total_invested=invested, unrealized_profit=value - invested,
        portfolio_roi_pct=risk.roi(value - invested, invested),
        realized_pnl=float(closed["realized_pnl"].sum()),
        portfolio_volatility=m["volatility"], sharpe=m["sharpe"], beta=m["beta"],
        max_drawdown=m["max_drawdown"], cagr=m["cagr"],
        num_clients=int(ds.clients["client_id"].nunique()),
        best_asset=None if best is None else best["asset_name"],
        best_asset_roi_pct=None if best is None else float(best["roi_pct"]),
        as_of=ds.as_of,
    )


def client_summary(ds: Dataset) -> pd.DataFrame:
    """One row per client: valuation, returns, risk metrics, classification."""
    rows = []
    for c in ds.clients.itertuples():
        h = compute_holdings(ds, c.client_id)
        invested, value = float(h["invested"].sum()), float(h["market_value"].sum())
        ps = client_series(ds, c.client_id)
        m = risk.analyze_series(ps, ds.benchmark)
        rows.append(dict(
            client_id=c.client_id, client=c.full_name, risk_appetite=c.risk_appetite,
            objective=c.investment_objective, num_holdings=len(h), invested=invested,
            market_value=value, unrealized_pnl=value - invested, roi_pct=risk.roi(value - invested, invested),
            realized_pnl=float(compute_holdings(ds, c.client_id, True)["realized_pnl"].sum()),
            cagr=m["cagr"], volatility=m["volatility"], sharpe=m["sharpe"], beta=m["beta"],
            max_drawdown=m["max_drawdown"], risk_class=m["risk_class"],
            alignment=risk.risk_alignment(c.risk_appetite, m["risk_class"]),
        ))
    return pd.DataFrame(rows)


def allocation(h: pd.DataFrame, by: str = "asset_class") -> pd.DataFrame:
    a = h.groupby(by, as_index=False)["market_value"].sum()
    a["weight"] = a["market_value"] / a["market_value"].sum()
    return a.sort_values("market_value", ascending=False).reset_index(drop=True)


def return_contributions(h: pd.DataFrame) -> pd.DataFrame:
    """Portfolio return = sum(invested weight x asset ROI)  (equals total ROI)."""
    d = h.copy()
    d["invested_weight"] = d["invested"] / d["invested"].sum()
    d["contribution_pct"] = d["invested_weight"] * d["roi_pct"]
    return d[["symbol", "asset_name", "asset_class", "invested_weight", "roi_pct", "contribution_pct"]]


def pnl_by_class(h: pd.DataFrame) -> pd.DataFrame:
    g = h.groupby("asset_class", as_index=False)[["invested", "market_value", "unrealized_pnl"]].sum()
    g["roi_pct"] = g["unrealized_pnl"] / g["invested"] * 100
    return g


def txn_amount(df: pd.DataFrame) -> pd.Series:
    return df["quantity"] * df["price"]
