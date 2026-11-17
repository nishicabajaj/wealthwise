"""Matplotlib charts (static): used by PDF reports and the docs screenshots."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from . import engine, risk  # noqa: E402

PALETTE = ["#0F4C81", "#2E8B57", "#E07B39", "#8E44AD", "#C0392B", "#16A085", "#7F8C8D"]


def _style(ax, title):
    ax.set_title(title, fontsize=11, fontweight="bold", loc="left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)


def allocation_pie(h, fig_size=(4.2, 3.4)):
    a = engine.allocation(h)
    fig, ax = plt.subplots(figsize=fig_size)
    ax.pie(a["market_value"], labels=a["asset_class"], autopct="%1.0f%%", startangle=90,
           colors=PALETTE, wedgeprops=dict(width=0.45, edgecolor="white"), textprops=dict(fontsize=8))
    ax.set_title("Asset allocation", fontsize=11, fontweight="bold", loc="left")
    fig.tight_layout()
    return fig


def growth_vs_benchmark(ps, bench, fig_size=(7, 3.2)):
    b = bench.reindex(ps.index).ffill()
    fig, ax = plt.subplots(figsize=fig_size)
    ax.plot(ps.index, ps["wealth"], color=PALETTE[0], lw=1.8, label="Portfolio (time-weighted)")
    ax.plot(ps.index, b / b.iloc[0] * 100, color=PALETTE[2], lw=1.4, label="NIFTY 50 (synthetic)")
    _style(ax, "Growth of 100 vs benchmark")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


def drawdown_chart(ps, fig_size=(7, 2.6)):
    fig, ax = plt.subplots(figsize=fig_size)
    ax.fill_between(ps.index, ps["drawdown"] * 100, 0, color=PALETTE[4], alpha=0.4)
    _style(ax, "Drawdown from peak (%)")
    fig.tight_layout()
    return fig


def monthly_returns_bar(ps, fig_size=(7, 2.8)):
    m = risk.monthly_returns(ps["wealth"]) * 100
    fig, ax = plt.subplots(figsize=fig_size)
    ax.bar(m.index, m.values, width=20, color=[PALETTE[1] if v >= 0 else PALETTE[4] for v in m.values])
    _style(ax, "Monthly returns (%)")
    fig.tight_layout()
    return fig
