"""Plotly figure builders for the Streamlit dashboard (interactive versions of the charts)."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

COLORS = ["#0F4C81", "#2E8B57", "#E07B39", "#8E44AD", "#C0392B", "#16A085", "#7F8C8D"]
LAYOUT = dict(margin=dict(l=10, r=10, t=45, b=10), template="plotly_white", legend=dict(orientation="h", y=-0.15))


def _fig(fig, title, height=340):
    fig.update_layout(title=title, height=height, **LAYOUT)
    return fig


def allocation_donut(alloc: pd.DataFrame, names="asset_class", title="Asset allocation"):
    fig = px.pie(alloc, names=names, values="market_value", hole=0.5, color_discrete_sequence=COLORS)
    fig.update_traces(textinfo="percent+label")
    return _fig(fig, title)


def growth_chart(ps: pd.DataFrame, bench: pd.Series, title="Growth of 100 vs benchmark"):
    b = bench.reindex(ps.index).ffill()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ps.index, y=ps["wealth"], name="Portfolio", line=dict(color=COLORS[0], width=2.2)))
    fig.add_trace(go.Scatter(x=ps.index, y=b / b.iloc[0] * 100, name="NIFTY 50 (synthetic)",
                             line=dict(color=COLORS[2], width=1.6)))
    return _fig(fig, title)


def monthly_returns_bar(m: pd.Series, title="Monthly returns"):
    df = pd.DataFrame({"month": m.index, "return_pct": m.values * 100})
    fig = px.bar(df, x="month", y="return_pct", color=df["return_pct"] >= 0,
                 color_discrete_map={True: COLORS[1], False: COLORS[4]})
    fig.update_layout(showlegend=False, yaxis_title="%")
    return _fig(fig, title)


def pnl_trend(ps: pd.DataFrame, title="Value vs net capital invested"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ps.index, y=ps["value"], name="Portfolio value", line=dict(color=COLORS[0])))
    fig.add_trace(go.Scatter(x=ps.index, y=ps["net_invested"], name="Net invested", line=dict(color=COLORS[6], dash="dot")))
    fig.add_trace(go.Scatter(x=ps.index, y=ps["pnl"], name="Profit / loss", fill="tozeroy",
                             line=dict(color=COLORS[1]), opacity=0.35))
    return _fig(fig, title)


def drawdown_area(ps: pd.DataFrame, title="Drawdown from peak"):
    fig = go.Figure(go.Scatter(x=ps.index, y=ps["drawdown"] * 100, fill="tozeroy", line=dict(color=COLORS[4])))
    fig.update_layout(yaxis_title="%")
    return _fig(fig, title, 280)


def aum_by_client(cs: pd.DataFrame, title="AUM by client"):
    d = cs.sort_values("market_value", ascending=False)
    fig = px.bar(d, x="client", y="market_value", color="risk_appetite", color_discrete_sequence=COLORS)
    fig.update_layout(xaxis_title=None, yaxis_title="₹")
    return _fig(fig, title)


def risk_return_scatter(cs: pd.DataFrame, title="Risk vs return by client"):
    d = cs.dropna(subset=["volatility", "cagr"]).copy()
    d["volatility_pct"], d["cagr_pct"] = d["volatility"] * 100, d["cagr"] * 100
    fig = px.scatter(d, x="volatility_pct", y="cagr_pct", size="market_value", color="risk_appetite",
                     hover_name="client", color_discrete_sequence=COLORS)
    fig.update_layout(xaxis_title="Annualised volatility (%)", yaxis_title="CAGR (%)")
    return _fig(fig, title, 420)


def heatmap_monthly(m: pd.Series, title="Monthly return heatmap (%)"):
    df = pd.DataFrame({"year": m.index.year, "month": m.index.month, "r": m.values * 100})
    pv = df.pivot(index="year", columns="month", values="r").reindex(columns=range(1, 13))
    fig = go.Figure(go.Heatmap(z=pv.values, x=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                               y=pv.index.astype(str), colorscale="RdYlGn", zmid=0, colorbar=dict(title="%")))
    return _fig(fig, title, 260)


def scenario_lines(proj: pd.DataFrame, title="Scenario projection"):
    fig = go.Figure()
    for s, c in zip(["Bear", "Base", "Bull"], [COLORS[4], COLORS[0], COLORS[1]]):
        fig.add_trace(go.Scatter(x=proj["year"], y=proj[s], name=s, line=dict(color=c, width=2.2)))
    fig.update_layout(xaxis_title="Years from now", yaxis_title="₹")
    return _fig(fig, title)


def monte_carlo_fan(pct: pd.DataFrame, title="Monte Carlo range (5th-95th percentile)"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pct["year"], y=pct["p95"], line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=pct["year"], y=pct["p5"], fill="tonexty", name="5th-95th",
                             line=dict(width=0), fillcolor="rgba(15,76,129,0.18)"))
    fig.add_trace(go.Scatter(x=pct["year"], y=pct["p75"], line=dict(width=0), showlegend=False))
    fig.add_trace(go.Scatter(x=pct["year"], y=pct["p25"], fill="tonexty", name="25th-75th",
                             line=dict(width=0), fillcolor="rgba(15,76,129,0.30)"))
    fig.add_trace(go.Scatter(x=pct["year"], y=pct["median"], name="Median", line=dict(color=COLORS[0], width=2.4)))
    fig.update_layout(xaxis_title="Years from now", yaxis_title="₹")
    return _fig(fig, title)


def rebalance_bars(rb: pd.DataFrame, title="Current vs target allocation"):
    fig = go.Figure()
    fig.add_trace(go.Bar(x=rb["asset_class"], y=rb["current_weight"] * 100, name="Current", marker_color=COLORS[0]))
    fig.add_trace(go.Bar(x=rb["asset_class"], y=rb["target_weight"] * 100, name="Target", marker_color=COLORS[2]))
    fig.update_layout(barmode="group", yaxis_title="%")
    return _fig(fig, title, 300)
