"""Investment performance reports (PDF via ReportLab, Excel via pandas)."""
from __future__ import annotations

import io
from pathlib import Path

import matplotlib
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import charts_mpl, config, engine, risk, scenarios
from .fmt import inr, pct
from .store import Dataset

NAVY = colors.HexColor("#0F4C81")


def _fonts():
    """Register DejaVu (ships with matplotlib) so the rupee sign renders."""
    try:
        base = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
        pdfmetrics.registerFont(TTFont("DejaVu", str(base / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(base / "DejaVuSans-Bold.ttf")))
        return "DejaVu", "DejaVu-Bold", "₹"
    except Exception:  # fall back to built-in fonts and "Rs."
        return "Helvetica", "Helvetica-Bold", "Rs. "


def _img(fig, width_cm):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=170)
    import matplotlib.pyplot as plt
    plt.close(fig)
    buf.seek(0)
    img = Image(buf)
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth, img.drawHeight = width_cm * cm, width_cm * cm * ratio
    return img


def _table(data, col_widths=None, font="DejaVu", bold="DejaVu-Bold", zebra=True):
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [("FONTNAME", (0, 0), (-1, -1), font), ("FONTSIZE", (0, 0), (-1, -1), 8),
             ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
             ("FONTNAME", (0, 0), (-1, 0), bold), ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
             ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC")),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if zebra:
        style += [("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6FA")])]
    t.setStyle(TableStyle(style))
    return t


def _styles(font, bold):
    ss = getSampleStyleSheet()
    return dict(
        h1=ParagraphStyle("h1", parent=ss["Title"], fontName=bold, fontSize=18, textColor=NAVY, alignment=0),
        h2=ParagraphStyle("h2", parent=ss["Heading2"], fontName=bold, fontSize=12, textColor=NAVY, spaceBefore=10),
        body=ParagraphStyle("b", parent=ss["BodyText"], fontName=font, fontSize=9),
        small=ParagraphStyle("s", parent=ss["BodyText"], fontName=font, fontSize=7, textColor=colors.grey),
    )


DISCLAIMER = ("Synthetic demonstration data - not real client information or live market prices. "
              "Projections use illustrative assumptions and are not investment advice.")


def client_report_pdf(ds: Dataset, client_id: str, horizon_years: int = 5) -> bytes:
    font, bold, sym = _fonts()
    S = _styles(font, bold)
    c = ds.client(client_id)
    h = engine.compute_holdings(ds, client_id)
    closed = engine.compute_holdings(ds, client_id, include_closed=True)
    ps = engine.client_series(ds, client_id)
    m = risk.analyze_series(ps, ds.benchmark)
    bc = risk.benchmark_comparison(ps, ds.benchmark)
    invested, value = h["invested"].sum(), h["market_value"].sum()
    R = lambda x: inr(x, sym)  # noqa: E731

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.4 * cm,
                            bottomMargin=1.4 * cm, title=f"WealthWise report - {c['full_name']}")
    st = [Paragraph("WealthWise - Investment Performance Report", S["h1"]),
          Paragraph(f"{c['full_name']} ({client_id}) &nbsp;|&nbsp; As of {ds.as_of:%d %b %Y}", S["body"]),
          Spacer(1, 6)]

    st.append(_table([["Profile", ""],
                      ["Risk appetite", c["risk_appetite"]], ["Objective", c["investment_objective"]],
                      ["Horizon (years)", str(c["investment_horizon_years"])],
                      ["Client since", f"{pd.Timestamp(c['join_date']):%d %b %Y}"]],
                     [5 * cm, 6 * cm], font, bold))
    st.append(Paragraph("Performance summary", S["h2"]))
    st.append(_table([
        ["Metric", "Value"],
        ["Invested amount", R(invested)], ["Current value", R(value)],
        ["Unrealised profit / loss", R(value - invested)],
        ["ROI", f"{risk.roi(value - invested, invested):.2f}%"],
        ["Realised profit / loss", R(closed['realized_pnl'].sum())],
        ["CAGR (time-weighted)", pct(m["cagr"])], ["Annualised volatility", pct(m["volatility"])],
        [f"Sharpe ratio (rf {config.RISK_FREE_RATE:.1%})", f"{m['sharpe']:.2f}"],
        ["Beta vs NIFTY 50", f"{m['beta']:.2f}"], ["Maximum drawdown", pct(m["max_drawdown"])],
        ["Risk classification", f"{m['risk_class']} ({risk.risk_alignment(c['risk_appetite'], m['risk_class']).lower()})"],
        ["Excess return vs benchmark", pct(bc["excess_return"])], ["Alpha (annualised)", pct(bc["alpha"])],
    ], [8 * cm, 5 * cm], font, bold))
    st += [Spacer(1, 6), _img(charts_mpl.growth_vs_benchmark(ps, ds.benchmark), 17), PageBreak()]

    st.append(Paragraph("Holdings", S["h2"]))
    rows = [["Asset", "Class", "Qty", "Avg cost", "Price", "Value", "P&L", "ROI %", "Wt %"]]
    for r in h.sort_values("market_value", ascending=False).itertuples():
        rows.append([r.asset_name[:26], r.asset_class, f"{r.quantity:,.2f}", f"{r.avg_cost:,.2f}",
                     f"{r.current_price:,.2f}", R(r.market_value), R(r.unrealized_pnl),
                     f"{r.roi_pct:.1f}", f"{r.weight * 100:.1f}"])
    st.append(_table(rows, [4.2 * cm, 2.1 * cm, 1.6 * cm, 1.7 * cm, 1.6 * cm, 2.4 * cm, 2.2 * cm, 1.2 * cm, 1.1 * cm], font, bold))
    st += [Spacer(1, 8), _img(charts_mpl.allocation_pie(h), 8.5)]

    rb = scenarios.rebalance_analysis(h, c["risk_appetite"])
    st.append(Paragraph("Rebalancing analysis", S["h2"]))
    rows = [["Asset class", "Current", "Target", "Drift (pp)", "Trade to target", "Action"]]
    for r in rb.itertuples():
        rows.append([r.asset_class, f"{r.current_weight:.1%}", f"{r.target_weight:.1%}",
                     f"{r.drift * 100:+.1f}", R(r.trade_amount), r.action])
    st.append(_table(rows, [3.5 * cm, 2.4 * cm, 2.4 * cm, 2.4 * cm, 3.6 * cm, 2 * cm], font, bold))

    proj, summ = scenarios.scenario_projection(value, scenarios.class_weights(h), horizon_years)
    st.append(Paragraph(f"Scenario analysis ({horizon_years}-year horizon, no new contributions)", S["h2"]))
    rows = [["Scenario", "Expected annual return", "Probability", "Projected value"]]
    for r in summ.itertuples():
        rows.append([r.scenario, f"{r.expected_annual_return:.2%}", f"{r.probability:.0%}", R(r.value_at_horizon)])
    st.append(_table(rows, [3.5 * cm, 4.5 * cm, 3 * cm, 4.5 * cm], font, bold))
    st += [Spacer(1, 8), _img(charts_mpl.drawdown_chart(ps), 17), Spacer(1, 6), Paragraph(DISCLAIMER, S["small"])]
    doc.build(st)
    return buf.getvalue()


def firm_report_pdf(ds: Dataset) -> bytes:
    font, bold, sym = _fonts()
    S = _styles(font, bold)
    R = lambda x: inr(x, sym)  # noqa: E731
    k = engine.firm_kpis(ds)
    cs = engine.client_summary(ds).sort_values("market_value", ascending=False)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.4 * cm, rightMargin=1.4 * cm, topMargin=1.4 * cm,
                            bottomMargin=1.4 * cm, title="WealthWise - firm report")
    st = [Paragraph("WealthWise - Firm Performance Report", S["h1"]),
          Paragraph(f"As of {k['as_of']:%d %b %Y}", S["body"]), Spacer(1, 6)]
    st.append(_table([["KPI", "Value"], ["Total AUM", R(k["total_aum"])], ["Total investments", R(k["total_invested"])],
                      ["Unrealised profit", R(k["unrealized_profit"])], ["Portfolio ROI", f"{k['portfolio_roi_pct']:.2f}%"],
                      ["Portfolio volatility (annualised)", pct(k["portfolio_volatility"])],
                      ["Number of clients", str(k["num_clients"])],
                      ["Best-performing asset", f"{k['best_asset']} ({k['best_asset_roi_pct']:.1f}%)"]],
                     [7 * cm, 8 * cm], font, bold))
    fs = engine.client_series(ds)
    st += [Spacer(1, 6), _img(charts_mpl.growth_vs_benchmark(fs, ds.benchmark), 17),
           Paragraph("Client league table", S["h2"])]
    rows = [["Client", "Risk", "Invested", "Value", "ROI %", "Vol", "Sharpe", "Beta", "MaxDD"]]
    for r in cs.itertuples():
        rows.append([r.client, r.risk_appetite, R(r.invested), R(r.market_value), f"{r.roi_pct:.1f}",
                     pct(r.volatility, 1), f"{r.sharpe:.2f}", f"{r.beta:.2f}", pct(r.max_drawdown, 1)])
    st.append(_table(rows, [3.3 * cm, 1.5 * cm, 2.6 * cm, 2.6 * cm, 1.3 * cm, 1.5 * cm, 1.5 * cm, 1.3 * cm, 1.6 * cm], font, bold))
    st += [Spacer(1, 6), Paragraph(DISCLAIMER, S["small"])]
    doc.build(st)
    return buf.getvalue()


def firm_excel_bytes(ds: Dataset) -> bytes:
    """Multi-sheet Excel export of the main analytical tables."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as xw:
        engine.client_summary(ds).to_excel(xw, sheet_name="Client summary", index=False)
        engine.compute_holdings(ds).to_excel(xw, sheet_name="Holdings", index=False)
        engine.asset_performance(engine.compute_holdings(ds)).to_excel(xw, sheet_name="Asset performance", index=False)
        ds.transactions.to_excel(xw, sheet_name="Transactions", index=False)
    return buf.getvalue()
