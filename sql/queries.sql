-- WealthWise analytical queries (portable SQL; tested on SQLite, written for MySQL 8).

-- Q1. Firm-wide KPIs: AUM, invested capital, unrealised profit, ROI
SELECT SUM(market_value)   AS total_aum,
       SUM(invested)       AS total_invested,
       SUM(unrealized_pnl) AS unrealized_profit,
       100.0 * SUM(unrealized_pnl) / SUM(invested) AS portfolio_roi_pct,
       COUNT(DISTINCT client_id) AS clients_with_holdings
FROM v_holdings;

-- Q2. AUM by asset class
SELECT asset_class,
       SUM(market_value) AS aum,
       100.0 * SUM(market_value) / (SELECT SUM(market_value) FROM v_holdings) AS pct_of_aum
FROM v_holdings
GROUP BY asset_class
ORDER BY aum DESC;

-- Q3. Best-performing asset by ROI on open positions
SELECT symbol, asset_name,
       SUM(invested) AS invested,
       SUM(market_value) AS market_value,
       100.0 * SUM(unrealized_pnl) / SUM(invested) AS roi_pct
FROM v_holdings
GROUP BY symbol, asset_name
ORDER BY roi_pct DESC
LIMIT 5;

-- Q4. Client league table
SELECT client_id, full_name, risk_appetite, num_holdings, invested, market_value,
       unrealized_pnl, roi_pct
FROM v_client_portfolio
ORDER BY market_value DESC;

-- Q5. Single-client allocation by asset class (replace C001)
SELECT asset_class,
       SUM(market_value) AS value,
       100.0 * SUM(market_value) / (SELECT SUM(market_value) FROM v_holdings WHERE client_id = 'C001') AS weight_pct
FROM v_holdings
WHERE client_id = 'C001'
GROUP BY asset_class;

-- Q6. Monthly transaction volume (use DATE_FORMAT(txn_date,'%Y-%m') on MySQL)
SELECT SUBSTR(txn_date, 1, 7) AS month,
       SUM(CASE WHEN txn_type = 'BUY'  THEN quantity * price ELSE 0 END) AS bought,
       SUM(CASE WHEN txn_type = 'SELL' THEN quantity * price ELSE 0 END) AS sold,
       COUNT(*) AS num_txns
FROM transactions
GROUP BY SUBSTR(txn_date, 1, 7)
ORDER BY month;

-- Q7. Clients whose equity-like exposure (Stock + Mutual Fund + ETF) exceeds 80%
SELECT client_id,
       100.0 * SUM(CASE WHEN asset_class <> 'Bond' THEN market_value ELSE 0 END) / SUM(market_value) AS equity_like_pct
FROM v_holdings
GROUP BY client_id
HAVING 100.0 * SUM(CASE WHEN asset_class <> 'Bond' THEN market_value ELSE 0 END) / SUM(market_value) > 80
ORDER BY equity_like_pct DESC;

-- Q8. Concentration: largest single position per client as % of that client's portfolio
SELECT h.client_id, h.symbol,
       100.0 * h.market_value / t.total AS pct_of_portfolio
FROM v_holdings h
JOIN (SELECT client_id, SUM(market_value) AS total FROM v_holdings GROUP BY client_id) t
  ON t.client_id = h.client_id
WHERE h.market_value = (SELECT MAX(h2.market_value) FROM v_holdings h2 WHERE h2.client_id = h.client_id)
ORDER BY pct_of_portfolio DESC;

-- Q9. Realised profit and loss by client (average-cost method)
SELECT client_id,
       SUM(sell_proceeds - sell_qty * buy_cost / buy_qty) AS realized_pnl
FROM v_positions
GROUP BY client_id
ORDER BY realized_pnl DESC;
