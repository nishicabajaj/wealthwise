"""Central configuration and every financial assumption used by WealthWise.

All numbers here are ASSUMPTIONS, not market facts. Change them in one place and
the Python engine, the Streamlit app and the Power BI export all follow.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
SQL_DIR = ROOT / "sql"
OUTPUT_DIR = ROOT / "outputs"
DB_PATH = DATA_DIR / "wealthwise.db"

# --- Market conventions -----------------------------------------------------
TRADING_DAYS = 252                 # annualisation factor for daily returns
RISK_FREE_RATE = 0.065             # assumption: roughly the 10-year G-Sec yield
BENCHMARK_CODE = "NIFTY50"
BENCHMARK_NAME = "NIFTY 50 (synthetic series)"

ASSET_CLASSES = ["Stock", "Mutual Fund", "ETF", "Bond"]
RISK_LEVELS = ["Low", "Medium", "High"]

# --- Risk classification (annualised volatility bands) ----------------------
# vol < LOW_MAX -> Low ; LOW_MAX <= vol < MEDIUM_MAX -> Medium ; else High
RISK_BANDS = (0.07, 0.12)

# --- Rebalancing -------------------------------------------------------------
# Target asset-class mix by client risk appetite (each row sums to 100%).
TARGET_ALLOCATION = {
    "Low":    {"Stock": 0.10, "Mutual Fund": 0.15, "ETF": 0.10, "Bond": 0.65},
    "Medium": {"Stock": 0.30, "Mutual Fund": 0.30, "ETF": 0.15, "Bond": 0.25},
    "High":   {"Stock": 0.45, "Mutual Fund": 0.30, "ETF": 0.15, "Bond": 0.10},
}
REBALANCE_THRESHOLD = 0.05         # flag a class when |drift| >= 5 percentage points

# --- Forward-looking scenarios (illustrative annual returns by asset class) --
SCENARIO_RETURNS = {
    "Bear": {"Stock": -0.05, "Mutual Fund": -0.03, "ETF": -0.02, "Bond": 0.045},
    "Base": {"Stock": 0.12,  "Mutual Fund": 0.11,  "ETF": 0.10,  "Bond": 0.07},
    "Bull": {"Stock": 0.22,  "Mutual Fund": 0.19,  "ETF": 0.18,  "Bond": 0.085},
}
SCENARIO_PROBABILITIES = {"Bear": 0.25, "Base": 0.50, "Bull": 0.25}
