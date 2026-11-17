# WealthWise - Financial Portfolio Modeling and Investment Analytics System

A data-driven wealth-management platform: register clients, track stocks / mutual funds / ETFs / bonds, value
portfolios, measure return and risk, compare with a benchmark, run scenarios and rebalancing analysis, and report
through Streamlit, Excel and Power BI.

> **All data is synthetic.** Clients, transactions and price histories are generated (`src/wealthwise/data_gen.py`);
> mutual-fund and bond series are fictitious, and no figure here is real market data or investment advice.
> `scripts/fetch_yahoo.py` can pull real NSE history when you have internet access.

## Architecture
```
 data_gen.py (synthetic clients, prices, transactions)  ·  fetch_yahoo.py (optional real prices)
                         │
            SQL database  (SQLite default · MySQL 8 supported)
      clients · assets · prices · benchmark_prices · transactions  +  views v_holdings, v_client_portfolio
                         │
        Python engine (pandas / NumPy):  engine.py · risk.py · scenarios.py
              │                 │                       │
       Excel model        Streamlit app           Power BI star-schema
   (live formulas,       (7 pages, Plotly,        (CSVs + DAX + theme)
    client selector)      PDF/Excel reports)
```

## Quick start
```bash
pip install -r requirements.txt
python scripts/build_db.py             # creates data/wealthwise.db + CSV copies (seeded, reproducible)
streamlit run app/streamlit_app.py     # interactive platform
python -m unittest discover -s tests   # 20 tests
python scripts/build_excel.py          # rebuild the Excel model (then recalc, see below)
python scripts/export_powerbi.py       # star-schema CSVs for Power BI
python scripts/generate_reports.py     # PDF per client + firm report -> outputs/reports/
```
**MySQL:** `pip install sqlalchemy pymysql`, create the database (`mysql < sql/schema_mysql.sql`), then
`export WEALTHWISE_DB_URL="mysql+pymysql://user:pass@localhost:3306/wealthwise"` and run `python scripts/build_db.py`.
Every script and the app read the same variable. `sql/queries.sql` holds 9 analytical queries.

## Modules (as in the brief)
| Module | Where |
|---|---|
| 1 Client management (registration, profiles, objectives, risk appetite, history) | `clients`/`transactions` tables, *Manage data* + *Client portfolio* pages |
| 2 Investment management (records, cost, market value, allocation, transactions) | `engine.compute_holdings`, `v_holdings` view |
| 3 Financial modelling engine (valuation, P&L, ROI, CAGR, scenarios, rebalancing) | `engine.py`, `risk.py`, `scenarios.py` |
| 4 Risk analysis engine (std-dev, volatility, Sharpe, beta, max drawdown, classification) | `risk.py` |
| 5 Analytics dashboard | Streamlit app, `powerbi/` |

## Formulas implemented (`risk.py`, `engine.py`)
| Metric | Implementation |
|---|---|
| Portfolio value | Σ quantity × current price |
| Profit/Loss | current value − invested amount |
| ROI | profit ÷ invested × 100 |
| CAGR | (ending ÷ beginning)^(1/n) − 1 (portfolio CAGR is computed on the time-weighted wealth index) |
| Portfolio return | Σ invested weight × asset ROI (`return_contributions`; equals total ROI - tested) |
| Volatility | sample std-dev of daily returns × √252 |
| Sharpe | (annualised return − risk-free rate) ÷ volatility; risk-free = 6.5 % (editable) |
| Beta | Cov(portfolio, benchmark) ÷ Var(benchmark) |
| Maximum drawdown | min(wealth ÷ running peak − 1), with peak and trough dates |

The brief's example (₹5,00,000 → ₹5,75,000: profit ₹75,000, ROI 15 %) is a unit test and also sits on the Excel
`Formulas` sheet.

## Conventions and assumptions (all in `config.py`)
* **Cost basis:** average cost = total buy cost ÷ total units bought; realised P&L = sell proceeds − units sold × average cost.
  The Python engine and the SQL views use the same rule (a test compares them).
* **Time-weighted returns:** each day's return uses the previous day's positions, so deposits/SIPs/withdrawals
  don't distort volatility, Sharpe, beta or drawdown.
* **Risk class:** annualised volatility < 7 % Low, < 12 % Medium, otherwise High; each client is also flagged
  *Aligned / Above appetite / Below appetite* against the stated risk appetite.
* **Targets and scenarios:** target asset-class mixes by risk appetite, Bear/Base/Bull class returns and probabilities
  are illustrative assumptions, editable in `config.py`, the app, and the Excel `Assumptions` sheet.
* The synthetic benchmark is the market factor that drives every asset, which is why betas look realistic.
* Benchmark return series use price levels only (no dividends/coupons); bond and fund series behave as total-return NAVs.

## Current synthetic dataset (seed 42, prices to 06-Nov-2026)
25 clients · 21 assets · 845 transactions · AUM ₹4.67 crore · invested ₹4.24 crore · unrealised profit ₹42.7 lakh ·
ROI 10.07 % · annualised volatility 8.3 % · best asset by ROI: Tata Consultancy Services. (The brief's KPI table is illustrative; yours
will differ.) Sample charts: `docs/screenshots/`.

## Excel model
`excel/WealthWise_Financial_Model.xlsx` - choose a client on **Portfolio!B2**; Portfolio, Scenarios, Rebalancing and
Risk_Returns recalculate with live formulas (SUMIFS, INDEX/MATCH, SUMPRODUCT, COVAR/VARP, STDEV…). Blue = inputs,
black = formulas, green = cross-sheet links. Verified: figures match the Python engine to the last digit for valuation,
scenarios and rebalancing. The Excel risk metrics back-test *current* holdings at month-ends (static weights), so they
differ slightly from the Python engine's transaction-aware daily series (`engine.static_backtest` reproduces the Excel
method). If you rebuild it, recalculate with LibreOffice or just open it in Excel (it recalculates on load).

## Power BI
`powerbi/` has the CSV star-schema, 20+ DAX measures, a theme and a page-by-page guide. A `.pbix` can only be authored in
Power BI Desktop, so it is not included - assembly takes about 30 minutes (see `powerbi/README.md`).

## Testing
`tests/test_engine.py` covers each formula against hand-calculated values, holdings/average-cost logic, time-weighted
returns with cash flows, SQL-view vs Python parity, KPI consistency, rebalancing and scenario invariants.
`tests/smoke_app.py` executes each Streamlit page's logic against stand-in modules (no rendering).

## Mapping to the 10-14 day roadmap
Days 1-2 concepts + data (`data_gen.py`) · 3-4 SQL (`sql/`) · 5-6 Python engine · 7-8 Excel model · 9-10 Power BI ·
11-12 Streamlit · 13-14 tests, this README, screenshots, GitHub (CI in `.github/workflows`).

## Known limitations
* Streamlit/Plotly rendering and the MySQL path were written to spec but **not executed** in the build sandbox (no internet to
  install them); everything else above was run and tested. Expect to fix small cosmetic issues on first launch.
* No transaction costs, taxes, dividends/coupons, FX, intraday data or holiday calendar (business days Mon-Fri).
* No authentication - add it before any real use. Not investment advice.
