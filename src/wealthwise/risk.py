"""Risk and return formulas (Module 4 + the formula table in the brief)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


# ---- Return formulas --------------------------------------------------------
def profit_loss(current_value: float, invested: float) -> float:
    """Profit/Loss = Current value - Invested amount."""
    return current_value - invested


def roi(profit: float, invested: float) -> float:
    """ROI (%) = Profit / Invested x 100."""
    return float("nan") if not invested else profit / invested * 100.0


def cagr(beginning: float, ending: float, years: float) -> float:
    """CAGR = (Ending / Beginning) ** (1 / n) - 1."""
    if beginning <= 0 or years <= 0:
        return float("nan")
    return (ending / beginning) ** (1.0 / years) - 1.0


def weighted_return(weights, returns) -> float:
    """Portfolio return = sum(weight_i x return_i)."""
    return float(np.dot(np.asarray(weights, float), np.asarray(returns, float)))


# ---- Risk formulas ----------------------------------------------------------
def annualized_return(returns: pd.Series, periods: int = config.TRADING_DAYS) -> float:
    r = returns.dropna()
    if len(r) == 0:
        return float("nan")
    return float(np.prod(1 + r) ** (periods / len(r)) - 1)


def volatility(returns: pd.Series, periods: int = config.TRADING_DAYS) -> float:
    """Standard deviation of periodic returns (sample), annualised."""
    r = returns.dropna()
    return float(r.std(ddof=1) * np.sqrt(periods)) if len(r) > 1 else float("nan")


def sharpe_ratio(ann_return: float, ann_vol: float, rf: float = config.RISK_FREE_RATE) -> float:
    """Sharpe = (Portfolio return - Risk-free rate) / Portfolio volatility."""
    return float("nan") if not ann_vol or np.isnan(ann_vol) else (ann_return - rf) / ann_vol


def beta(returns: pd.Series, bench_returns: pd.Series) -> float:
    """Beta = Cov(portfolio, benchmark) / Var(benchmark)."""
    df = pd.concat([returns, bench_returns], axis=1, join="inner").dropna()
    if len(df) < 3:
        return float("nan")
    cov = np.cov(df.iloc[:, 0], df.iloc[:, 1], ddof=1)
    return float(cov[0, 1] / cov[1, 1]) if cov[1, 1] else float("nan")


def drawdown_series(wealth: pd.Series) -> pd.Series:
    return wealth / wealth.cummax() - 1.0


def max_drawdown(wealth: pd.Series):
    """Largest peak-to-trough decline. Returns (mdd as negative fraction, peak date, trough date)."""
    w = wealth.dropna()
    if w.empty:
        return float("nan"), None, None
    dd = drawdown_series(w)
    trough = dd.idxmin()
    peak = w.loc[:trough].idxmax()
    return float(dd.min()), peak, trough


def classify_risk(vol: float) -> str:
    if vol is None or np.isnan(vol):
        return "n/a"
    lo, hi = config.RISK_BANDS
    return "Low" if vol < lo else ("Medium" if vol < hi else "High")


def risk_alignment(appetite: str, risk_class: str) -> str:
    order = {"Low": 0, "Medium": 1, "High": 2}
    if risk_class not in order:
        return "n/a"
    d = order[risk_class] - order[appetite]
    return "Aligned" if d == 0 else ("Above appetite" if d > 0 else "Below appetite")


# ---- Bundles ----------------------------------------------------------------
def analyze_series(ps: pd.DataFrame, bench: pd.Series, rf: float = config.RISK_FREE_RATE) -> dict:
    """Full metric set from a portfolio_series() frame."""
    nan = float("nan")
    if ps is None or len(ps) < 3:
        return dict(twr=nan, cagr=nan, ann_return=nan, volatility=nan, sharpe=nan, beta=nan,
                    max_drawdown=nan, mdd_peak=None, mdd_trough=None, risk_class="n/a")
    ret = ps["ret"].iloc[1:]
    years = (ps.index[-1] - ps.index[0]).days / 365.25
    w0, w1 = float(ps["wealth"].iloc[0]), float(ps["wealth"].iloc[-1])
    ann = annualized_return(ret)
    vol = volatility(ret)
    mdd, peak, trough = max_drawdown(ps["wealth"])
    b_ret = bench.reindex(ps.index).pct_change()
    return dict(twr=w1 / w0 - 1, cagr=cagr(w0, w1, years), ann_return=ann, volatility=vol,
                sharpe=sharpe_ratio(ann, vol, rf), beta=beta(ret, b_ret.iloc[1:]),
                max_drawdown=mdd, mdd_peak=peak, mdd_trough=trough, risk_class=classify_risk(vol))


def benchmark_comparison(ps: pd.DataFrame, bench: pd.Series, rf: float = config.RISK_FREE_RATE) -> dict:
    """Portfolio vs benchmark over the portfolio's own lifetime."""
    nan = float("nan")
    if ps is None or len(ps) < 3:
        return dict(portfolio_return=nan, benchmark_return=nan, excess_return=nan, alpha=nan,
                    beta=nan, tracking_error=nan, information_ratio=nan)
    b = bench.reindex(ps.index).ffill()
    p_ret, b_ret = ps["ret"].iloc[1:], b.pct_change().iloc[1:]
    p_tot, b_tot = ps["wealth"].iloc[-1] / ps["wealth"].iloc[0] - 1, b.iloc[-1] / b.iloc[0] - 1
    p_ann, b_ann = annualized_return(p_ret), annualized_return(b_ret)
    bt = beta(p_ret, b_ret)
    active = p_ret - b_ret
    te = float(active.std(ddof=1) * np.sqrt(config.TRADING_DAYS))
    return dict(portfolio_return=p_tot, benchmark_return=b_tot, excess_return=p_tot - b_tot,
                alpha=p_ann - (rf + bt * (b_ann - rf)),       # Jensen's alpha (annualised)
                beta=bt, tracking_error=te,
                information_ratio=(p_ann - b_ann) / te if te else nan)


def monthly_returns(wealth: pd.Series) -> pd.Series:
    """Month-end to month-end returns; first month measured from the series start."""
    if wealth is None or len(wealth) < 2:
        return pd.Series(dtype=float)
    me = wealth.resample("ME").last()
    prev = me.shift(1)
    prev.iloc[0] = wealth.iloc[0]
    return me / prev - 1.0
