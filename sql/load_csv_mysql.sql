-- Alternative to `python scripts/build_db.py` for MySQL: bulk-load the generated CSVs (data/csv/).
-- Requires: SET GLOBAL local_infile = 1;  and  mysql --local-infile=1 -u root -p
USE wealthwise;
SET FOREIGN_KEY_CHECKS = 0;
LOAD DATA LOCAL INFILE 'data/csv/clients.csv' INTO TABLE clients FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' IGNORE 1 LINES;
LOAD DATA LOCAL INFILE 'data/csv/assets.csv' INTO TABLE assets FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' IGNORE 1 LINES;
LOAD DATA LOCAL INFILE 'data/csv/prices.csv' INTO TABLE prices FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' IGNORE 1 LINES (price_date, asset_id, close_price);
LOAD DATA LOCAL INFILE 'data/csv/benchmark_prices.csv' INTO TABLE benchmark_prices FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' IGNORE 1 LINES;
LOAD DATA LOCAL INFILE 'data/csv/transactions.csv' INTO TABLE transactions FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"' IGNORE 1 LINES;
SET FOREIGN_KEY_CHECKS = 1;
