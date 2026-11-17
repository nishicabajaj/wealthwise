-- Portable views (work on both MySQL 8 and SQLite).
-- Cost-basis convention: average cost = total BUY cost / total units BOUGHT.
-- Realised P&L = SELL proceeds - units sold x average cost.

DROP VIEW IF EXISTS v_latest_price;
CREATE VIEW v_latest_price AS
SELECT p.asset_id, p.price_date, p.close_price
FROM prices p
JOIN (SELECT asset_id, MAX(price_date) AS last_date FROM prices GROUP BY asset_id) m
  ON m.asset_id = p.asset_id AND m.last_date = p.price_date;

DROP VIEW IF EXISTS v_positions;
CREATE VIEW v_positions AS
SELECT t.client_id,
       t.asset_id,
       SUM(CASE WHEN t.txn_type = 'BUY'  THEN t.quantity ELSE 0 END)           AS buy_qty,
       SUM(CASE WHEN t.txn_type = 'BUY'  THEN t.quantity * t.price ELSE 0 END) AS buy_cost,
       SUM(CASE WHEN t.txn_type = 'SELL' THEN t.quantity ELSE 0 END)           AS sell_qty,
       SUM(CASE WHEN t.txn_type = 'SELL' THEN t.quantity * t.price ELSE 0 END) AS sell_proceeds
FROM transactions t
GROUP BY t.client_id, t.asset_id;

DROP VIEW IF EXISTS v_holdings;
CREATE VIEW v_holdings AS
SELECT v.client_id,
       v.asset_id,
       a.symbol,
       a.asset_name,
       a.asset_class,
       v.buy_qty - v.sell_qty                                        AS quantity,
       v.buy_cost / v.buy_qty                                        AS avg_cost,
       (v.buy_qty - v.sell_qty) * (v.buy_cost / v.buy_qty)           AS invested,
       lp.close_price                                                AS current_price,
       (v.buy_qty - v.sell_qty) * lp.close_price                     AS market_value,
       (v.buy_qty - v.sell_qty) * (lp.close_price - v.buy_cost / v.buy_qty) AS unrealized_pnl,
       v.sell_proceeds - v.sell_qty * (v.buy_cost / v.buy_qty)       AS realized_pnl
FROM v_positions v
JOIN assets a         ON a.asset_id  = v.asset_id
JOIN v_latest_price lp ON lp.asset_id = v.asset_id
WHERE v.buy_qty - v.sell_qty > 0.000001;

DROP VIEW IF EXISTS v_client_portfolio;
CREATE VIEW v_client_portfolio AS
SELECT c.client_id,
       c.full_name,
       c.risk_appetite,
       COUNT(h.asset_id)                    AS num_holdings,
       SUM(h.invested)                      AS invested,
       SUM(h.market_value)                  AS market_value,
       SUM(h.unrealized_pnl)                AS unrealized_pnl,
       100.0 * SUM(h.unrealized_pnl) / NULLIF(SUM(h.invested), 0) AS roi_pct
FROM clients c
LEFT JOIN v_holdings h ON h.client_id = c.client_id
GROUP BY c.client_id, c.full_name, c.risk_appetite;
