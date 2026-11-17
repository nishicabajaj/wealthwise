"""Run:  python -m unittest discover -s tests -v   (pytest also works)"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wealthwise import config, data_gen, db, engine, fmt, risk, scenarios, store  # noqa: E402


def tiny_dataset(txns, prices, assets=None, bench=None):
    idx = pd.to_datetime(prices.index)
    prices = prices.copy(); prices.index = idx
    cols = list(prices.columns)
    assets = assets if assets is not None else pd.DataFrame({
        "asset_id": cols, "symbol": cols, "asset_name": cols, "asset_class": "Stock", "sector": "X"})
    t = pd.DataFrame(txns, columns=["client_id", "asset_id", "txn_date", "txn_type", "quantity", "price"])
    t["txn_date"] = pd.to_datetime(t["txn_date"])
    clients = pd.DataFrame({"client_id": ["C1"], "full_name": ["T"], "risk_appetite": ["Medium"],
                            "investment_objective": ["x"], "join_date": [idx[0]]})
    bench = bench if bench is not None else pd.Series(100.0, index=idx)
    return store.Dataset(clients, assets, t, prices, bench)


class BriefFormulas(unittest.TestCase):
    def test_example_from_brief(self):          # Rs 5,00,000 -> Rs 5,75,000 in one year
        p = risk.profit_loss(575_000, 500_000)
        self.assertEqual(p, 75_000)
        self.assertAlmostEqual(risk.roi(p, 500_000), 15.0)
        self.assertAlmostEqual(risk.cagr(500_000, 575_000, 1), 0.15)

    def test_cagr_multi_year(self):
        self.assertAlmostEqual(risk.cagr(100, 121, 2), 0.10)

    def test_weighted_return(self):
        self.assertAlmostEqual(risk.weighted_return([0.6, 0.4], [0.10, 0.20]), 0.14)

    def test_volatility_constant_is_zero_and_matches_numpy(self):
        self.assertAlmostEqual(risk.volatility(pd.Series([0.01] * 50)), 0.0)
        r = pd.Series(np.random.default_rng(1).normal(0, 0.01, 300))
        self.assertAlmostEqual(risk.volatility(r), r.std(ddof=1) * np.sqrt(252))

    def test_sharpe(self):
        self.assertAlmostEqual(risk.sharpe_ratio(0.15, 0.10, rf=0.05), 1.0)

    def test_beta(self):
        b = pd.Series(np.random.default_rng(2).normal(0, 0.01, 200))
        self.assertAlmostEqual(risk.beta(2 * b, b), 2.0)
        self.assertAlmostEqual(risk.beta(b, b), 1.0)

    def test_max_drawdown(self):
        w = pd.Series([100, 120, 90, 110, 80, 130], index=pd.date_range("2024-01-01", periods=6))
        mdd, peak, trough = risk.max_drawdown(w)
        self.assertAlmostEqual(mdd, 80 / 120 - 1)
        self.assertEqual(peak, w.index[1]); self.assertEqual(trough, w.index[4])

    def test_classification(self):
        self.assertEqual([risk.classify_risk(v) for v in (0.05, 0.10, 0.20)], ["Low", "Medium", "High"])

    def test_fmt_indian_grouping(self):
        self.assertEqual(fmt.inr(1234567), "₹12,34,567")
        self.assertEqual(fmt.inr(500000), "₹5,00,000")
        self.assertEqual(fmt.inr(-75000), "-₹75,000")


class HoldingsAndSeries(unittest.TestCase):
    def setUp(self):
        prices = pd.DataFrame({"A": [100, 110, 121, 121]}, index=["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"])
        txns = [("C1", "A", "2024-01-01", "BUY", 10, 100),
                ("C1", "A", "2024-01-02", "BUY", 10, 110),
                ("C1", "A", "2024-01-04", "SELL", 5, 121)]
        self.ds = tiny_dataset(txns, prices)

    def test_average_cost_and_pnl(self):
        h = engine.compute_holdings(self.ds, "C1").iloc[0]
        self.assertAlmostEqual(h.quantity, 15)
        self.assertAlmostEqual(h.avg_cost, 105)                  # (1000 + 1100) / 20
        self.assertAlmostEqual(h.invested, 15 * 105)
        self.assertAlmostEqual(h.market_value, 15 * 121)
        self.assertAlmostEqual(h.unrealized_pnl, 15 * 16)
        self.assertAlmostEqual(h.realized_pnl, 5 * (121 - 105))

    def test_time_weighted_return_ignores_cash_flows(self):
        ps = engine.client_series(self.ds, "C1")
        # +10% on day 2 (10 units), +10% on day 3 (20 units): TWR = 21% despite the extra deposit
        self.assertAlmostEqual(ps["wealth"].iloc[2] / 100 - 1, 0.21, places=9)

    def test_pnl_trend_equals_value_minus_net_cash_in(self):
        ps = engine.client_series(self.ds, "C1")
        self.assertAlmostEqual(ps["pnl"].iloc[2], 20 * 121 - (10 * 100 + 10 * 110))

    def test_return_contributions_sum_to_total_roi(self):
        h = engine.compute_holdings(self.ds, "C1")
        c = engine.return_contributions(h)
        self.assertAlmostEqual(c["contribution_pct"].sum(), h["unrealized_pnl"].sum() / h["invested"].sum() * 100)


class FullPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = db.connect("sqlite:///:memory:")
        db.init_schema(cls.conn)
        for name, df in data_gen.generate_all(seed=3).items():
            db.write_frame(cls.conn, name, df)
        cls.ds = store.load_dataset(cls.conn)

    def test_no_negative_positions_ever(self):
        pos, _ = engine.position_matrix(self.ds)
        for cid in self.ds.clients.client_id:
            p, _ = engine.position_matrix(self.ds, [cid])
            self.assertGreaterEqual(p.min().min(), -1e-6, cid)

    def test_sql_view_matches_python_engine(self):
        sql = db.read(self.conn, "SELECT client_id, asset_id, quantity, invested, market_value FROM v_holdings")
        py = engine.compute_holdings(self.ds)
        m = sql.merge(py, on=["client_id", "asset_id"], suffixes=("_sql", "_py"))
        self.assertEqual(len(m), len(py)); self.assertEqual(len(sql), len(py))
        np.testing.assert_allclose(m.market_value_sql, m.market_value_py, rtol=1e-9)
        np.testing.assert_allclose(m.invested_sql, m.invested_py, rtol=1e-9)

    def test_kpis_consistent(self):
        k = engine.firm_kpis(self.ds)
        self.assertAlmostEqual(k["unrealized_profit"], k["total_aum"] - k["total_invested"])
        self.assertAlmostEqual(k["portfolio_roi_pct"], k["unrealized_profit"] / k["total_invested"] * 100)
        self.assertEqual(k["num_clients"], 25)
        cs = engine.client_summary(self.ds)
        self.assertAlmostEqual(cs.market_value.sum(), k["total_aum"], places=4)

    def test_weights_sum_to_one_per_client(self):
        w = engine.compute_holdings(self.ds).groupby("client_id")["weight"].sum()
        np.testing.assert_allclose(w, 1.0)

    def test_rebalance_trades_net_to_zero_without_new_cash(self):
        h = engine.compute_holdings(self.ds, "C001")
        r = scenarios.rebalance_analysis(h, "Medium")
        self.assertAlmostEqual(r["trade_amount"].sum(), 0.0, places=4)
        self.assertAlmostEqual(r["target_weight"].sum(), 1.0)

    def test_scenarios_ordered_and_monte_carlo_runs(self):
        h = engine.compute_holdings(self.ds, "C001")
        proj, s = scenarios.scenario_projection(h.market_value.sum(), scenarios.class_weights(h), 5, 50_000)
        self.assertTrue(proj["Bear"].iloc[-1] < proj["Base"].iloc[-1] < proj["Bull"].iloc[-1])
        ps = engine.client_series(self.ds, "C001")
        pct, st = scenarios.monte_carlo(ps["ret"], h.market_value.sum(), 3, n_sims=500)
        self.assertTrue((pct["p5"] <= pct["median"]).all() and (pct["median"] <= pct["p95"]).all())

    def test_best_asset_is_max_roi(self):
        perf = engine.asset_performance(engine.compute_holdings(self.ds))
        self.assertEqual(perf.iloc[0].roi_pct, perf.roi_pct.max())


if __name__ == "__main__":
    unittest.main()
