-- WealthWise schema for MySQL 8.x
-- Run:  mysql -u root -p < sql/schema_mysql.sql   (creates database wealthwise)

CREATE DATABASE IF NOT EXISTS wealthwise CHARACTER SET utf8mb4;
USE wealthwise;

CREATE TABLE IF NOT EXISTS clients (
    client_id               VARCHAR(10)  PRIMARY KEY,
    full_name               VARCHAR(100) NOT NULL,
    email                   VARCHAR(120) UNIQUE,
    phone                   VARCHAR(20),
    city                    VARCHAR(60),
    date_of_birth           DATE,
    occupation              VARCHAR(80),
    annual_income           DECIMAL(14,2) CHECK (annual_income >= 0),
    risk_appetite           ENUM('Low','Medium','High') NOT NULL,
    investment_objective    VARCHAR(60),
    investment_horizon_years INT CHECK (investment_horizon_years > 0),
    join_date               DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
    asset_id     VARCHAR(10) PRIMARY KEY,
    symbol       VARCHAR(30) NOT NULL UNIQUE,
    asset_name   VARCHAR(120) NOT NULL,
    asset_class  ENUM('Stock','Mutual Fund','ETF','Bond') NOT NULL,
    sector       VARCHAR(60),
    currency     CHAR(3) NOT NULL DEFAULT 'INR',
    data_source  VARCHAR(30) NOT NULL DEFAULT 'synthetic'
);

CREATE TABLE IF NOT EXISTS prices (
    asset_id    VARCHAR(10) NOT NULL,
    price_date  DATE NOT NULL,
    close_price DECIMAL(14,4) NOT NULL CHECK (close_price > 0),
    PRIMARY KEY (asset_id, price_date),
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
);

CREATE TABLE IF NOT EXISTS benchmark_prices (
    benchmark_code VARCHAR(20) NOT NULL,
    price_date     DATE NOT NULL,
    close_value    DECIMAL(14,4) NOT NULL CHECK (close_value > 0),
    PRIMARY KEY (benchmark_code, price_date)
);

CREATE TABLE IF NOT EXISTS transactions (
    txn_id     INT AUTO_INCREMENT PRIMARY KEY,
    client_id  VARCHAR(10) NOT NULL,
    asset_id   VARCHAR(10) NOT NULL,
    txn_date   DATE NOT NULL,
    txn_type   ENUM('BUY','SELL') NOT NULL,
    quantity   DECIMAL(16,4) NOT NULL CHECK (quantity > 0),
    price      DECIMAL(14,4) NOT NULL CHECK (price > 0),
    notes      VARCHAR(120),
    FOREIGN KEY (client_id) REFERENCES clients(client_id),
    FOREIGN KEY (asset_id)  REFERENCES assets(asset_id)
);

CREATE INDEX idx_txn_client_date ON transactions (client_id, txn_date);
CREATE INDEX idx_txn_asset       ON transactions (asset_id);
CREATE INDEX idx_prices_date     ON prices (price_date);
