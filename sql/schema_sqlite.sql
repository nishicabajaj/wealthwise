-- WealthWise schema for SQLite (local zero-setup default). Same tables as MySQL.

CREATE TABLE IF NOT EXISTS clients (
    client_id               TEXT PRIMARY KEY,
    full_name               TEXT NOT NULL,
    email                   TEXT UNIQUE,
    phone                   TEXT,
    city                    TEXT,
    date_of_birth           TEXT,
    occupation              TEXT,
    annual_income           REAL CHECK (annual_income >= 0),
    risk_appetite           TEXT NOT NULL CHECK (risk_appetite IN ('Low','Medium','High')),
    investment_objective    TEXT,
    investment_horizon_years INTEGER CHECK (investment_horizon_years > 0),
    join_date               TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
    asset_id     TEXT PRIMARY KEY,
    symbol       TEXT NOT NULL UNIQUE,
    asset_name   TEXT NOT NULL,
    asset_class  TEXT NOT NULL CHECK (asset_class IN ('Stock','Mutual Fund','ETF','Bond')),
    sector       TEXT,
    currency     TEXT NOT NULL DEFAULT 'INR',
    data_source  TEXT NOT NULL DEFAULT 'synthetic'
);

CREATE TABLE IF NOT EXISTS prices (
    asset_id    TEXT NOT NULL REFERENCES assets(asset_id),
    price_date  TEXT NOT NULL,
    close_price REAL NOT NULL CHECK (close_price > 0),
    PRIMARY KEY (asset_id, price_date)
);

CREATE TABLE IF NOT EXISTS benchmark_prices (
    benchmark_code TEXT NOT NULL,
    price_date     TEXT NOT NULL,
    close_value    REAL NOT NULL CHECK (close_value > 0),
    PRIMARY KEY (benchmark_code, price_date)
);

CREATE TABLE IF NOT EXISTS transactions (
    txn_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id  TEXT NOT NULL REFERENCES clients(client_id),
    asset_id   TEXT NOT NULL REFERENCES assets(asset_id),
    txn_date   TEXT NOT NULL,
    txn_type   TEXT NOT NULL CHECK (txn_type IN ('BUY','SELL')),
    quantity   REAL NOT NULL CHECK (quantity > 0),
    price      REAL NOT NULL CHECK (price > 0),
    notes      TEXT
);

CREATE INDEX IF NOT EXISTS idx_txn_client_date ON transactions (client_id, txn_date);
CREATE INDEX IF NOT EXISTS idx_txn_asset       ON transactions (asset_id);
CREATE INDEX IF NOT EXISTS idx_prices_date     ON prices (price_date);
