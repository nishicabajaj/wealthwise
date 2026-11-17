"""OPTIONAL: replace synthetic prices with real Yahoo Finance history (needs internet + `pip install yfinance`).

Only assets whose symbol ends in .NS (NSE-listed stocks and ETFs) are fetched; the synthetic mutual fund and bond
series are kept. The NIFTY 50 benchmark (^NSEI) is replaced too. Run AFTER scripts/build_db.py:

    python scripts/fetch_yahoo.py

NOTE: existing transactions were priced from the synthetic series, so their purchase prices will not match real
history. Use this to explore real price data, or reload your own transactions afterwards. This script has not been
run in the build environment (no internet there).
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wealthwise import config, data_gen, db  # noqa: E402

try:
    import yfinance as yf
except ImportError:
    sys.exit("Install yfinance first:  pip install yfinance")

conn = db.connect()
assets = db.read(conn, "SELECT asset_id, symbol FROM assets WHERE symbol LIKE '%.NS'")
start, end = data_gen.START_DATE, data_gen.END_DATE
frames = []
for r in assets.itertuples():
    px = yf.download(r.symbol, start=start, end=end, auto_adjust=True, progress=False)["Close"].squeeze().dropna()
    if px.empty:
        print("no data for", r.symbol); continue
    db.execute(conn, "DELETE FROM prices WHERE asset_id = :a", {"a": r.asset_id})
    df = pd.DataFrame({"asset_id": r.asset_id, "price_date": px.index, "close_price": px.round(2).values})
    db.write_frame(conn, "prices", df)
    print("updated", r.symbol, len(df))
bm = yf.download("^NSEI", start=start, end=end, auto_adjust=True, progress=False)["Close"].squeeze().dropna()
db.execute(conn, "DELETE FROM benchmark_prices WHERE benchmark_code = :b", {"b": config.BENCHMARK_CODE})
db.write_frame(conn, "benchmark_prices", pd.DataFrame({"benchmark_code": config.BENCHMARK_CODE,
                                                       "price_date": bm.index, "close_value": bm.values}))
print("benchmark updated", len(bm))
