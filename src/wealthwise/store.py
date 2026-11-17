"""Load the database into an in-memory Dataset used by the analytics engine."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import config, db


@dataclass
class Dataset:
    clients: pd.DataFrame
    assets: pd.DataFrame
    transactions: pd.DataFrame
    prices: pd.DataFrame        # wide: index = trading date, columns = asset_id
    benchmark: pd.Series        # index = trading date

    @property
    def latest_prices(self) -> pd.Series:
        return self.prices.ffill().iloc[-1]

    @property
    def as_of(self) -> pd.Timestamp:
        return self.prices.index[-1]

    def client(self, client_id: str) -> pd.Series:
        return self.clients.set_index("client_id").loc[client_id]


def load_dataset(conn) -> Dataset:
    clients = db.read(conn, "SELECT * FROM clients ORDER BY client_id")
    clients["join_date"] = pd.to_datetime(clients["join_date"])
    assets = db.read(conn, "SELECT * FROM assets ORDER BY asset_id")
    txns = db.read(conn, "SELECT * FROM transactions ORDER BY txn_date, txn_id")
    txns["txn_date"] = pd.to_datetime(txns["txn_date"])
    for col in ("quantity", "price"):
        txns[col] = txns[col].astype(float)

    prices = db.read(conn, "SELECT asset_id, price_date, close_price FROM prices")
    prices["price_date"] = pd.to_datetime(prices["price_date"])
    prices["close_price"] = prices["close_price"].astype(float)
    wide = prices.pivot(index="price_date", columns="asset_id", values="close_price").sort_index()
    wide = wide.ffill()

    bench = db.read(
        conn,
        f"SELECT price_date, close_value FROM benchmark_prices "
        f"WHERE benchmark_code = '{config.BENCHMARK_CODE}'",
    )
    bench["price_date"] = pd.to_datetime(bench["price_date"])
    bench_s = bench.set_index("price_date")["close_value"].astype(float).sort_index()
    bench_s = bench_s.reindex(wide.index).ffill()
    return Dataset(clients, assets, txns, wide, bench_s)
