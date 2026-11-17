"""WealthWise - interactive wealth management platform.   Run:  streamlit run app/streamlit_app.py"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import charts  # noqa: E402
from wealthwise import config, db, engine, reports, risk, scenarios, store  # noqa: E402
from wealthwise.fmt import inr, inr_short, pct  # noqa: E402

st.set_page_config(page_title="WealthWise", page_icon="💹", layout="wide")

if "ver" not in st.session_state:
    st.session_state["ver"] = 0


# ---------------------------------------------------------------- data access
@st.cache_data(show_spinner="Loading data…")
def get_ds(ver: int):
    conn = db.connect()
    try:
        return store.load_dataset(conn)
    finally:
        conn.close()


@st.cache_data(show_spinner="Computing client analytics…")
def get_summary(ver: int):
    return engine.client_summary(get_ds(ver))


@st.cache_data(show_spinner=False)
def get_kpis(ver: int):
    return engine.firm_kpis(get_ds(ver))


def refresh():
    st.session_state["ver"] += 1
    st.cache_data.clear()
    st.rerun()


ver = st.session_state["ver"]
if not config.DB_PATH.exists() and not __import__("os").getenv("WEALTHWISE_DB_URL"):
    # First launch (e.g. on Streamlit Community Cloud): build the synthetic database automatically.
    from wealthwise import data_gen  # noqa: E402

    with st.spinner("First launch: building the synthetic database (about 30 seconds)..."):
        _conn = db.connect()
        db.init_schema(_conn, drop_existing=True)
        _frames = data_gen.generate_all(42)
        for _t in ("clients", "assets", "prices", "benchmark_prices", "transactions"):
            db.write_frame(_conn, _t, _frames[_t])
        _conn.close()
ds = get_ds(ver)
if ds.clients.empty:
    st.warning("No clients yet - add one under 'Manage data'.")

# --------------------------------------------------------------------- sidebar
st.sidebar.title("💹 WealthWise")
page = st.sidebar.radio("Navigate", ["Dashboard", "Client portfolio", "Risk analysis", "Benchmark comparison",
                                     "Scenarios & rebalancing", "Manage data", "Reports"])
st.sidebar.caption(f"Prices as of {ds.as_of:%d %b %Y}\n\nSynthetic demo data - not real client or market data.")
rf = st.sidebar.number_input("Risk-free rate (%)", 0.0, 15.0, config.RISK_FREE_RATE * 100, 0.25) / 100


def client_picker(label="Client", key=None):
    opts = ds.clients.set_index("client_id")["full_name"]
    cid = st.selectbox(label, opts.index, format_func=lambda c: f"{c} - {opts[c]}", key=key)
    return cid


def kpi(col, label, value, help_=None):
    col.metric(label, value, help=help_)


# ------------------------------------------------------------------- Dashboard
if page == "Dashboard":
    st.title("Wealth management dashboard")
    k, cs = get_kpis(ver), get_summary(ver)
    c = st.columns(4)
    kpi(c[0], "Total AUM", inr(k["total_aum"]), "Current market value of all holdings")
    kpi(c[1], "Total investments", inr(k["total_invested"]), "Cost basis of open positions")
    kpi(c[2], "Unrealised profit", inr(k["unrealized_profit"]))
    kpi(c[3], "Portfolio ROI", f"{k['portfolio_roi_pct']:.2f}%")
    c = st.columns(4)
    kpi(c[0], "Portfolio volatility", pct(k["portfolio_volatility"]), "Annualised, from time-weighted daily returns")
    kpi(c[1], "Number of clients", str(k["num_clients"]))
    kpi(c[2], "Best-performing asset", k["best_asset"] or "-", f"ROI {k['best_asset_roi_pct']:.1f}%" if k["best_asset"] else None)
    kpi(c[3], "Realised P&L", inr(k["realized_pnl"]))

    h = engine.compute_holdings(ds)
    fs = engine.client_series(ds)
    a, b = st.columns(2)
    a.plotly_chart(charts.allocation_donut(engine.allocation(h)), key="d_alloc")
    b.plotly_chart(charts.aum_by_client(cs), key="d_aum")
    a, b = st.columns(2)
    a.plotly_chart(charts.growth_chart(fs, ds.benchmark, "Firm growth of 100 vs benchmark"), key="d_growth")
    b.plotly_chart(charts.pnl_trend(fs, "Firm value, net invested and P&L"), key="d_pnl")
    a, b = st.columns(2)
    a.plotly_chart(charts.monthly_returns_bar(risk.monthly_returns(fs["wealth"]), "Firm monthly returns"), key="d_mr")
    b.plotly_chart(charts.risk_return_scatter(cs), key="d_rr")

    st.subheader("Client-wise comparison")
    view = cs[["client", "risk_appetite", "invested", "market_value", "unrealized_pnl", "roi_pct", "cagr",
               "volatility", "sharpe", "beta", "max_drawdown", "risk_class"]].copy()
    for col in ("cagr", "volatility", "max_drawdown"):
        view[col] = view[col] * 100
    st.dataframe(view.round(2), hide_index=True)
    st.subheader("Asset performance (all clients)")
    st.dataframe(engine.asset_performance(h).round(2), hide_index=True)

# ------------------------------------------------------------ Client portfolio
elif page == "Client portfolio":
    st.title("Client portfolio")
    cid = client_picker()
    cl = ds.client(cid)
    h = engine.compute_holdings(ds, cid)
    ps = engine.client_series(ds, cid)
    m = risk.analyze_series(ps, ds.benchmark, rf)
    inv, val = h["invested"].sum(), h["market_value"].sum()
    st.caption(f"{cl['occupation']} · {cl['city']} · Objective: {cl['investment_objective']} · "
               f"Horizon {cl['investment_horizon_years']} yrs · Risk appetite **{cl['risk_appetite']}**")
    if h.empty:
        st.info("This client has no holdings yet.")
    else:
        c = st.columns(5)
        kpi(c[0], "Invested", inr(inv)); kpi(c[1], "Current value", inr(val))
        kpi(c[2], "Profit / loss", inr(val - inv)); kpi(c[3], "ROI", f"{risk.roi(val - inv, inv):.2f}%")
        kpi(c[4], "CAGR (time-weighted)", pct(m["cagr"]))
        a, b = st.columns([1, 2])
        a.plotly_chart(charts.allocation_donut(engine.allocation(h)), key="c_alloc")
        b.plotly_chart(charts.pnl_trend(ps), key="c_pnl")
        st.plotly_chart(charts.heatmap_monthly(risk.monthly_returns(ps["wealth"])), key="c_heat")
        st.subheader("Holdings")
        st.dataframe(h[["asset_name", "asset_class", "quantity", "avg_cost", "current_price", "invested",
                        "market_value", "unrealized_pnl", "roi_pct", "weight"]].round(2), hide_index=True)
    st.subheader("Investment history")
    t = ds.transactions[ds.transactions["client_id"] == cid].merge(ds.assets[["asset_id", "asset_name"]], on="asset_id")
    t["amount"] = t["quantity"] * t["price"]
    st.dataframe(t[["txn_date", "asset_name", "txn_type", "quantity", "price", "amount", "notes"]]
                 .sort_values("txn_date", ascending=False), hide_index=True)

# --------------------------------------------------------------- Risk analysis
elif page == "Risk analysis":
    st.title("Risk analysis")
    cs = get_summary(ver)
    st.plotly_chart(charts.risk_return_scatter(cs), key="r_rr")
    st.caption(f"Risk class from annualised volatility: Low < {config.RISK_BANDS[0]:.0%}, "
               f"Medium < {config.RISK_BANDS[1]:.0%}, High above. Sharpe uses the risk-free rate in the sidebar "
               f"(table below uses the configured default {config.RISK_FREE_RATE:.1%}).")
    show = cs[["client", "risk_appetite", "risk_class", "alignment", "volatility", "sharpe", "beta", "max_drawdown"]].copy()
    for col in ("volatility", "max_drawdown"):
        show[col] = (show[col] * 100).round(2)
    st.dataframe(show.round(2), hide_index=True)
    st.subheader("Single client")
    cid = client_picker(key="risk_client")
    ps = engine.client_series(ds, cid)
    m = risk.analyze_series(ps, ds.benchmark, rf)
    if len(ps) > 2:
        c = st.columns(5)
        kpi(c[0], "Volatility", pct(m["volatility"])); kpi(c[1], "Sharpe", f"{m['sharpe']:.2f}")
        kpi(c[2], "Beta", f"{m['beta']:.2f}"); kpi(c[3], "Max drawdown", pct(m["max_drawdown"]))
        kpi(c[4], "Risk class", m["risk_class"])
        if m["mdd_peak"] is not None:
            st.caption(f"Worst drawdown: peak {m['mdd_peak']:%d %b %Y} → trough {m['mdd_trough']:%d %b %Y}")
        st.plotly_chart(charts.drawdown_area(ps), key="r_dd")
    else:
        st.info("Not enough history for risk metrics.")

# ------------------------------------------------------ Benchmark comparison
elif page == "Benchmark comparison":
    st.title("Benchmark comparison")
    scope = st.radio("Scope", ["Client", "Whole firm"], horizontal=True)
    cid = client_picker() if scope == "Client" else None
    ps = engine.client_series(ds, cid)
    if len(ps) < 3:
        st.info("Not enough history.")
    else:
        bc = risk.benchmark_comparison(ps, ds.benchmark, rf)
        c = st.columns(4)
        kpi(c[0], "Portfolio return", pct(bc["portfolio_return"])); kpi(c[1], "Benchmark return", pct(bc["benchmark_return"]))
        kpi(c[2], "Excess return", pct(bc["excess_return"])); kpi(c[3], "Alpha (annualised)", pct(bc["alpha"]))
        c = st.columns(3)
        kpi(c[0], "Beta", f"{bc['beta']:.2f}"); kpi(c[1], "Tracking error", pct(bc["tracking_error"]))
        kpi(c[2], "Information ratio", f"{bc['information_ratio']:.2f}")
        st.plotly_chart(charts.growth_chart(ps, ds.benchmark), key="b_growth")
        pm = risk.monthly_returns(ps["wealth"])
        bw = ds.benchmark.reindex(ps.index).ffill()
        bm = risk.monthly_returns(bw / bw.iloc[0] * 100)
        cmp_ = pd.DataFrame({"Portfolio %": pm * 100, "Benchmark %": bm * 100}).round(2)
        cmp_.index = cmp_.index.strftime("%b %Y")
        st.dataframe(cmp_)

# ----------------------------------------------------- Scenarios & rebalancing
elif page == "Scenarios & rebalancing":
    st.title("Scenarios & rebalancing")
    cid = client_picker()
    cl = ds.client(cid)
    h = engine.compute_holdings(ds, cid)
    if h.empty:
        st.info("This client has no holdings yet.")
        st.stop()
    value = float(h["market_value"].sum())
    tab1, tab2, tab3 = st.tabs(["Scenario analysis", "Monte Carlo", "Rebalancing"])
    with tab1:
        a, b = st.columns(2)
        years = a.slider("Horizon (years)", 1, 20, 5)
        contrib = b.number_input("Annual contribution (₹)", 0, 10_000_000, 0, 10_000)
        st.caption("Expected annual return by asset class (editable assumptions)")
        assum = {}
        cols = st.columns(3)
        for col, s in zip(cols, ["Bear", "Base", "Bull"]):
            col.markdown(f"**{s}**")
            assum[s] = {k: col.number_input(f"{s} · {k} (%)", -50.0, 60.0, v * 100, 0.5, key=f"{s}{k}") / 100
                        for k, v in config.SCENARIO_RETURNS[s].items()}
        proj, summ = scenarios.scenario_projection(value, scenarios.class_weights(h), years, contrib, assum)
        st.plotly_chart(charts.scenario_lines(proj), key="s_lines")
        out = summ.copy()
        out["expected_annual_return"] = (out["expected_annual_return"] * 100).round(2)
        out["probability"] = (out["probability"] * 100).round(0)
        out["value_at_horizon"] = out["value_at_horizon"].round(0)
        out["gain_vs_contributed"] = out["gain_vs_contributed"].round(0)
        st.dataframe(out, hide_index=True)
        st.metric("Probability-weighted value at horizon", inr(scenarios.probability_weighted_value(summ)))
    with tab2:
        ps = engine.client_series(ds, cid)
        c1, c2 = st.columns(2)
        mc_years = c1.slider("Horizon (years)", 1, 20, 5, key="mcy")
        mc_contrib = c2.number_input("Annual contribution (₹)", 0, 10_000_000, 0, 10_000, key="mcc")
        try:
            pct_df, stats = scenarios.monte_carlo(ps["ret"], value, mc_years, mc_contrib)
            st.plotly_chart(charts.monte_carlo_fan(pct_df), key="s_mc")
            c = st.columns(4)
            kpi(c[0], "Median outcome", inr_short(stats["median"])); kpi(c[1], "5th percentile", inr_short(stats["p5"]))
            kpi(c[2], "95th percentile", inr_short(stats["p95"]))
            kpi(c[3], "Chance of ending below capital in", f"{stats['prob_loss']:.1%}")
            st.caption("Bootstraps this client's historical daily returns (2,000 paths). Past returns do not guarantee future results.")
        except ValueError as e:
            st.info(str(e))
    with tab3:
        thr = st.slider("Drift threshold (percentage points)", 1, 15, int(config.REBALANCE_THRESHOLD * 100)) / 100
        cash = st.number_input("New cash to invest (₹)", 0, 100_000_000, 0, 10_000)
        rb = scenarios.rebalance_analysis(h, cl["risk_appetite"], thr, cash)
        st.plotly_chart(charts.rebalance_bars(rb), key="s_rb")
        st.caption(f"Target mix for a **{cl['risk_appetite']}** risk appetite (config.py).")
        if rb["needs_rebalance"].any():
            st.warning("Rebalancing recommended: " + ", ".join(rb.loc[rb["needs_rebalance"], "asset_class"]))
        else:
            st.success("Portfolio is within the drift threshold.")
        view = rb.copy()
        for col in ("current_weight", "target_weight", "drift"):
            view[col] = (view[col] * 100).round(1)
        for col in ("current_value", "target_value", "trade_amount"):
            view[col] = view[col].round(0)
        st.dataframe(view.drop(columns="needs_rebalance"), hide_index=True)

# ----------------------------------------------------------------- Manage data
elif page == "Manage data":
    st.title("Manage data")
    t1, t2 = st.tabs(["Register client", "Record transaction"])
    with t1:
        with st.form("new_client", clear_on_submit=True):
            a, b = st.columns(2)
            name = a.text_input("Full name"); email = b.text_input("Email")
            city = a.text_input("City"); occ = b.text_input("Occupation")
            income = a.number_input("Annual income (₹)", 0, 1_000_000_000, 1_000_000, 50_000)
            dob = b.date_input("Date of birth", pd.Timestamp("1990-01-01"), min_value=pd.Timestamp("1930-01-01"))
            risk_ap = a.selectbox("Risk appetite", config.RISK_LEVELS, index=1)
            obj = b.text_input("Investment objective", "Wealth Creation")
            hz = a.number_input("Horizon (years)", 1, 40, 10)
            if st.form_submit_button("Register client"):
                if not name.strip():
                    st.error("Name is required.")
                else:
                    nums = ds.clients["client_id"].str[1:].astype(int)
                    new_id = f"C{(nums.max() if len(nums) else 0) + 1:03d}"
                    conn = db.connect()
                    try:
                        db.execute(conn, "INSERT INTO clients (client_id, full_name, email, city, date_of_birth, occupation, "
                                         "annual_income, risk_appetite, investment_objective, investment_horizon_years, join_date) "
                                         "VALUES (:i,:n,:e,:c,:d,:o,:a,:r,:ob,:h,:j)",
                                   dict(i=new_id, n=name.strip(), e=email or None, c=city, d=pd.Timestamp(dob).strftime('%Y-%m-%d'), o=occ, a=income,
                                        r=risk_ap, ob=obj, h=int(hz), j=str(pd.Timestamp.today().date())))
                    except Exception as exc:  # e.g. duplicate email
                        st.error(f"Could not save: {exc}")
                    else:
                        st.success(f"Registered {new_id}")
                        conn.close(); refresh()
                    finally:
                        try: conn.close()
                        except Exception: pass
    with t2:
        cid = client_picker(key="txn_client")
        a_opts = ds.assets.set_index("asset_id")
        aid = st.selectbox("Asset", a_opts.index, format_func=lambda x: f"{a_opts.at[x, 'asset_name']} ({a_opts.at[x, 'asset_class']})")
        c1, c2, c3, c4 = st.columns(4)
        ttype = c1.selectbox("Type", ["BUY", "SELL"])
        d = c2.date_input("Date", ds.as_of, min_value=ds.prices.index[0], max_value=ds.as_of)
        px_series = ds.prices[aid]
        default_px = float(px_series[px_series.index <= pd.Timestamp(d)].iloc[-1]) if (px_series.index <= pd.Timestamp(d)).any() else 1.0
        qty = c3.number_input("Quantity", 0.0, 1e9, 10.0, 1.0)
        price = c4.number_input("Price (₹)", 0.01, 1e9, default_px, 0.5, key=f"px_{aid}_{d}")
        if st.button("Save transaction"):
            tx = ds.transactions[(ds.transactions.client_id == cid) & (ds.transactions.asset_id == aid)
                                 & (ds.transactions.txn_date <= pd.Timestamp(d))]
            held = (tx.quantity.where(tx.txn_type == "BUY", -tx.quantity)).sum()
            if qty <= 0:
                st.error("Quantity must be positive.")
            elif ttype == "SELL" and qty > held + 1e-9:
                st.error(f"Cannot sell {qty:g}: only {held:g} units held on that date.")
            else:
                conn = db.connect()
                db.execute(conn, "INSERT INTO transactions (client_id, asset_id, txn_date, txn_type, quantity, price, notes) "
                                 "VALUES (:c,:a,:d,:t,:q,:p,:n)",
                           dict(c=cid, a=aid, d=pd.Timestamp(d).strftime('%Y-%m-%d'), t=ttype, q=qty, p=price, n="Entered in app"))
                conn.close(); refresh()
    st.subheader("Clients")
    st.dataframe(ds.clients, hide_index=True)

# --------------------------------------------------------------------- Reports
else:
    st.title("Reports")
    st.write("Generate investment performance reports as PDF or Excel.")
    cid = client_picker()
    a, b, c = st.columns(3)
    if a.button("Build client PDF"):
        st.session_state["client_pdf"] = reports.client_report_pdf(ds, cid)
    if "client_pdf" in st.session_state:
        a.download_button("⬇ Download client report", st.session_state["client_pdf"], f"{cid}_report.pdf", "application/pdf")
    if b.button("Build firm PDF"):
        st.session_state["firm_pdf"] = reports.firm_report_pdf(ds)
    if "firm_pdf" in st.session_state:
        b.download_button("⬇ Download firm report", st.session_state["firm_pdf"], "firm_report.pdf", "application/pdf")
    if c.button("Build Excel export"):
        st.session_state["xlsx"] = reports.firm_excel_bytes(ds)
    if "xlsx" in st.session_state:
        c.download_button("⬇ Download Excel", st.session_state["xlsx"], "wealthwise_export.xlsx",
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
