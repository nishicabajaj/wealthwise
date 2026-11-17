"""Export a star-schema of CSVs for Power BI Desktop to powerbi/data/.

Tables: dim_client, dim_asset, dim_date, fact_transactions, fact_holdings, fact_portfolio_daily,
        fact_firm_daily, fact_benchmark_daily, fact_monthly_returns, fact_client_metrics
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wealthwise import config, db, engine, risk, store  # noqa: E402

out = config.ROOT / "powerbi" / "data"
out.mkdir(parents=True, exist_ok=True)
ds = store.load_dataset(db.connect())

dim_client = ds.clients.copy()
dim_asset = ds.assets.copy()
idx = ds.prices.index
dim_date = pd.DataFrame({"date": idx})
dim_date["year"], dim_date["month_num"] = idx.year, idx.month
dim_date["month_name"] = idx.strftime("%b")
dim_date["year_month"] = idx.strftime("%Y-%m")
dim_date["quarter"] = "Q" + idx.quarter.astype(str)
dim_date["is_month_end"] = ~pd.Series(idx.to_period("M")).duplicated(keep="last").values

tx = ds.transactions.copy()
tx["amount"] = tx["quantity"] * tx["price"]
tx["signed_amount"] = tx["amount"].where(tx["txn_type"] == "BUY", -tx["amount"])

daily, monthly = [], []
bench = ds.benchmark
for cid in ds.clients["client_id"]:
    ps = engine.client_series(ds, cid)
    if ps.empty:
        continue
    d = ps.reset_index(names="date"); d.insert(0, "client_id", cid); daily.append(d)
    pm = risk.monthly_returns(ps["wealth"])
    bw = bench.reindex(ps.index).ffill()
    bmr = risk.monthly_returns(bw / bw.iloc[0] * 100)
    monthly.append(pd.DataFrame({"client_id": cid, "month_end": pm.index, "portfolio_return": pm.values,
                                 "benchmark_return": bmr.reindex(pm.index).values}))
firm = engine.client_series(ds).reset_index(names="date")
bdf = pd.DataFrame({"date": bench.index, "level": bench.values})
bdf["daily_return"] = bdf["level"].pct_change()
bdf["rebased_100"] = bdf["level"] / bdf["level"].iloc[0] * 100

tables = {
    "dim_client": dim_client, "dim_asset": dim_asset, "dim_date": dim_date,
    "fact_transactions": tx, "fact_holdings": engine.compute_holdings(ds),
    "fact_portfolio_daily": pd.concat(daily), "fact_firm_daily": firm, "fact_benchmark_daily": bdf,
    "fact_monthly_returns": pd.concat(monthly), "fact_client_metrics": engine.client_summary(ds),
}
for name, df in tables.items():
    df.to_csv(out / f"{name}.csv", index=False, date_format="%Y-%m-%d")
    print(f"{name:<22}{len(df):>8,} rows")
print("written to", out)
