"""Scenario analysis, Monte Carlo projection and rebalancing (Module 3)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def class_weights(h: pd.DataFrame) -> pd.Series:
    w = h.groupby("asset_class")["market_value"].sum().reindex(config.ASSET_CLASSES, fill_value=0.0)
    return w / w.sum() if w.sum() > 0 else w


def expected_return(weights: pd.Series, class_returns: dict) -> float:
    return float(sum(weights.get(k, 0.0) * class_returns[k] for k in class_returns))


def scenario_projection(value: float, weights: pd.Series, years: int = 5, annual_contribution: float = 0.0,
                        assumptions: dict | None = None, probs: dict | None = None):
    """Year-by-year value under Bear/Base/Bull. Contributions are added at year end.
    Returns (projection frame, summary frame)."""
    assumptions = assumptions or config.SCENARIO_RETURNS
    probs = probs or config.SCENARIO_PROBABILITIES
    rates = {s: expected_return(weights, r) for s, r in assumptions.items()}
    proj = pd.DataFrame({"year": range(0, years + 1)})
    for s, r in rates.items():
        v, path = value, [value]
        for _ in range(years):
            v = v * (1 + r) + annual_contribution
            path.append(v)
        proj[s] = path
    contributed = value + annual_contribution * years
    summary = pd.DataFrame({
        "scenario": list(rates), "expected_annual_return": list(rates.values()),
        "probability": [probs[s] for s in rates],
        "value_at_horizon": [proj[s].iloc[-1] for s in rates],
    })
    summary["gain_vs_contributed"] = summary["value_at_horizon"] - contributed
    return proj, summary


def probability_weighted_value(summary: pd.DataFrame) -> float:
    return float((summary["probability"] * summary["value_at_horizon"]).sum())


def monte_carlo(daily_returns: pd.Series, value: float, years: int = 5, annual_contribution: float = 0.0,
                n_sims: int = 2000, seed: int = 7):
    """Bootstrap historical daily portfolio returns. Returns (percentile paths, stats)."""
    r = daily_returns.dropna().to_numpy()
    if len(r) < 30:
        raise ValueError("Need at least 30 daily returns for a Monte Carlo projection.")
    rng = np.random.default_rng(seed)
    td = config.TRADING_DAYS
    draws = rng.choice(r, size=(n_sims, years * td), replace=True)
    vals = np.full(n_sims, float(value))
    paths = [vals.copy()]
    for y in range(years):
        vals = vals * np.prod(1 + draws[:, y * td:(y + 1) * td], axis=1) + annual_contribution
        paths.append(vals.copy())
    paths = np.array(paths)
    pct = pd.DataFrame(np.percentile(paths, [5, 25, 50, 75, 95], axis=1).T,
                       columns=["p5", "p25", "median", "p75", "p95"])
    pct.insert(0, "year", range(years + 1))
    contributed = value + annual_contribution * years
    stats = dict(median=float(np.median(paths[-1])), p5=float(np.percentile(paths[-1], 5)),
                 p95=float(np.percentile(paths[-1], 95)),
                 prob_loss=float((paths[-1] < contributed).mean()), contributed=contributed)
    return pct, stats


def rebalance_analysis(h: pd.DataFrame, appetite: str, threshold: float = config.REBALANCE_THRESHOLD,
                       new_cash: float = 0.0, targets: dict | None = None) -> pd.DataFrame:
    """Compare current asset-class mix with the target for the client's risk appetite.
    trade_amount > 0 means buy, < 0 means sell (full move back to target)."""
    targets = targets or config.TARGET_ALLOCATION[appetite]
    cur = h.groupby("asset_class")["market_value"].sum().reindex(config.ASSET_CLASSES, fill_value=0.0)
    total_now = float(cur.sum())
    total = total_now + new_cash
    cur_w = cur / total_now if total_now > 0 else cur * 0
    tgt_w = pd.Series({k: targets.get(k, 0.0) for k in config.ASSET_CLASSES})
    out = pd.DataFrame({
        "asset_class": config.ASSET_CLASSES, "current_value": cur.values, "current_weight": cur_w.values,
        "target_weight": tgt_w.values, "drift": (cur_w - tgt_w).values,
        "target_value": (tgt_w * total).values,
    })
    out["trade_amount"] = out["target_value"] - out["current_value"]
    out["action"] = np.where(out["drift"].abs() < threshold, "Hold",
                             np.where(out["trade_amount"] > 0, "Buy", "Sell"))
    out["needs_rebalance"] = out["drift"].abs() >= threshold
    return out
