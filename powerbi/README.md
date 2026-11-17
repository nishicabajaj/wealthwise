# Power BI dashboard - build guide (about 30 minutes)

A `.pbix` file can only be created inside Power BI Desktop, so this folder gives you everything needed to
assemble it quickly: a clean star-schema of CSVs, all DAX measures, a theme and the page layout.

## 1. Load the data
```bash
python scripts/export_powerbi.py          # writes powerbi/data/*.csv
```
Power BI Desktop → **Get data → Text/CSV** → load every file in `powerbi/data/`.
(To read the live MySQL database instead: Get data → MySQL database → pick the same tables / views.)

## 2. Model (Model view → create these relationships, all one-to-many, single direction)
| From (one) | To (many) |
|---|---|
| dim_client[client_id] | fact_holdings[client_id], fact_transactions[client_id], fact_portfolio_daily[client_id], fact_monthly_returns[client_id], fact_client_metrics[client_id] |
| dim_asset[asset_id] | fact_holdings[asset_id], fact_transactions[asset_id] |
| dim_date[date] | fact_portfolio_daily[date], fact_firm_daily[date], fact_benchmark_daily[date], fact_transactions[txn_date] |

Mark `dim_date` as the date table. Set `dim_date[month_name]` to sort by `month_num`.

## 3. Measures and theme
* Create a blank table named **Measures** and paste `WealthWise_measures.dax` (one measure at a time).
* View → Themes → **Browse for themes** → `WealthWise_theme.json`.

## 4. Pages
**Page 1 - Executive overview**
* Cards: Total AUM · Total Investments · Unrealized Profit · Portfolio ROI % · Firm Volatility · Number of Clients · Best Performing Asset
* Donut: `dim_asset[asset_class]` × Total AUM (asset allocation)
* Clustered bar: `dim_client[full_name]` × Total AUM, legend = risk_appetite (client-wise comparison)
* Line: `fact_firm_daily[wealth]` and `fact_benchmark_daily[rebased_100]` by date (performance vs benchmark)
* Slicers: risk_appetite, asset_class

**Page 2 - Client portfolio** (slicer: client)
* Cards: Latest Portfolio Value, Latest Profit / Loss, Portfolio ROI %, CAGR
* Area: `fact_portfolio_daily` value, net_invested, pnl by date (profit/loss trend)
* Column: `fact_monthly_returns[portfolio_return]` by month_end (monthly returns); add benchmark_return as a line
* Table: fact_holdings (asset_name, quantity, avg_cost, market_value, unrealized_pnl, roi_pct)

**Page 3 - Risk & return**
* Scatter: X = `fact_client_metrics[volatility]`, Y = `cagr`, size = `market_value`, legend = risk_appetite
* Table: client, risk_class, alignment, volatility, sharpe, beta, max_drawdown (conditional-format `max_drawdown` and `alignment`)
* Area: `fact_portfolio_daily[drawdown]` for the selected client

## 5. Publish
File → Publish → Power BI Service; schedule a refresh if the source is the MySQL database.
Commit a screenshot of each page to `docs/screenshots/` for the GitHub README.
