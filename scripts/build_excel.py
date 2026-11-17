"""Build excel/WealthWise_Financial_Model.xlsx - a formula-driven model fed by the database.

Pick a client on the Portfolio sheet (cell B2) and every sheet recalculates:
valuation, P&L, ROI, allocation, scenarios, rebalancing and monthly risk metrics.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openpyxl import Workbook  # noqa: E402
from openpyxl.chart import LineChart, PieChart, Reference  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.utils import get_column_letter as L  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402

from wealthwise import config, db, engine, store  # noqa: E402

OUT = config.ROOT / "excel" / "WealthWise_Financial_Model.xlsx"
CUR = '"₹"#,##0;("₹"#,##0);"-"'
PCT = '0.0%;(0.0%);"-"'
PCT2 = '0.00%;(0.00%);"-"'
NUM = '#,##0.00'
QTY = '#,##0.000'
DATE = 'mmm-yy'
BLUE, BLACK, GREEN = "0000FF", "000000", "008000"
YELLOW = PatternFill("solid", fgColor="FFFF00")
HEAD = PatternFill("solid", fgColor="0F4C81")
GREY = PatternFill("solid", fgColor="F2F2F2")
thin = Side(style="thin", color="BFBFBF")


def put(ws, ref, value, kind=None, fmt=None, bold=False, fill=None, align=None):
    c = ws[ref]
    c.value = value
    if kind is None:
        kind = ("link" if isinstance(value, str) and value.startswith("=") and "!" in value
                else "calc" if isinstance(value, str) and value.startswith("=") else "label")
    color = {"input": BLUE, "link": GREEN}.get(kind, BLACK)
    c.font = Font(name="Arial", size=10, bold=bold, color=color)
    if fmt:
        c.number_format = fmt
    if fill:
        c.fill = fill
    if align:
        c.alignment = Alignment(horizontal=align)
    return c


def header(ws, row, labels, col=1):
    for i, t in enumerate(labels):
        c = ws.cell(row=row, column=col + i, value=t)
        c.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        c.fill = HEAD
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def title(ws, text, sub=None):
    ws["A1"].value = text
    ws["A1"].font = Font(name="Arial", size=14, bold=True, color="0F4C81")
    if sub:
        ws["A2"].value = sub
        ws["A2"].font = Font(name="Arial", size=9, italic=True, color="666666")


def widths(ws, spec):
    for col, w in spec.items():
        ws.column_dimensions[col].width = w


ds = store.load_dataset(db.connect())
h = engine.compute_holdings(ds)
clients, assets = ds.clients, ds.assets
NA, NC, NH = len(assets), len(clients), len(h)
CLASSES = config.ASSET_CLASSES
CLIENT_DEFAULT = "C010"

wb = Workbook()

# ------------------------------------------------------------------ Guide
g = wb.active; g.title = "Guide"
title(g, "WealthWise - Financial Model", f"Prices as of {ds.as_of:%d %b %Y}. All data is SYNTHETIC (see README).")
lines = [
    ("How to use", True),
    ("1. Go to the Portfolio sheet and choose a client in cell B2 (yellow dropdown).", False),
    ("2. Portfolio, Scenarios, Rebalancing and Risk_Returns recalculate for that client.", False),
    ("3. Change assumptions (risk-free rate, scenario returns, targets, thresholds) on the Assumptions sheet.", False),
    ("4. Holdings_Data, Assets, Clients and Prices_Monthly are data sheets exported from the SQL database.", False),
    ("", False),
    ("Colour legend", True),
    ("Blue text = hard-coded input / data.   Black = formula.   Green = formula linking to another sheet.", False),
    ("Yellow fill = key assumption or cell you are expected to change.", False),
    ("", False),
    ("Method notes and assumptions", True),
    ("Average cost = total BUY cost / total units bought (same convention as the SQL views and Python engine).", False),
    ("Risk metrics here are a back-test of the client's CURRENT holdings over 36 month-ends (static weights).", False),
    ("The Python engine uses transaction-aware, time-weighted daily returns, so volatility/Sharpe differ slightly.", False),
    ("Volatility = STDEV of monthly returns x SQRT(12). Beta = COVAR(portfolio, benchmark) / VARP(benchmark).", False),
    ("Sharpe = (annualised return - risk-free rate) / annualised volatility. Max drawdown = MIN(value / running peak - 1).", False),
    ("Scenario returns, target allocations and the 6.5% risk-free rate are illustrative assumptions, not forecasts.", False),
    ("Sheet 'Formulas' reproduces the worked example from the project brief (Rs 5,00,000 -> Rs 5,75,000).", False),
]
for i, (t, b) in enumerate(lines, start=4):
    put(g, f"A{i}", t, "label", bold=b)
widths(g, {"A": 120})

# ------------------------------------------------------------- Assumptions
a = wb.create_sheet("Assumptions")
title(a, "Assumptions", "Blue cells on yellow are editable levers. Percentages are stored as fractions.")
rows = [("Risk-free rate (annual)", config.RISK_FREE_RATE, PCT2, "Roughly the 10-year G-Sec yield (assumption)"),
        ("Rebalance threshold (abs. drift)", config.REBALANCE_THRESHOLD, PCT, "Flag a class when |drift| >= this"),
        ("Projection horizon (years, 1-10)", 5, "0", "Used on the Scenarios sheet"),
        ("Annual contribution (₹)", 0, CUR, "Added at the end of each projection year"),
        ("Risk band: Low below (annual vol)", config.RISK_BANDS[0], PCT, "Volatility < this = Low"),
        ("Risk band: Medium below (annual vol)", config.RISK_BANDS[1], PCT, "Volatility < this = Medium, else High")]
for i, (lab, val, fmt, note) in enumerate(rows, start=3):
    put(a, f"A{i}", lab)
    put(a, f"B{i}", val, "input", fmt, fill=YELLOW)
    put(a, f"C{i}", note, "label")
dv = DataValidation(type="whole", operator="between", formula1="1", formula2="10", showErrorMessage=True,
                    errorTitle="Horizon", error="Enter a whole number from 1 to 10")
a.add_data_validation(dv); dv.add("B5")

put(a, "A9", "Scenario annual returns by asset class (illustrative)", bold=True)
header(a, 10, ["Asset class", "Bear", "Base", "Bull"])
for i, k in enumerate(CLASSES, start=11):
    put(a, f"A{i}", k)
    for j, s in enumerate(["Bear", "Base", "Bull"]):
        put(a, f"{L(2 + j)}{i}", config.SCENARIO_RETURNS[s][k], "input", PCT, fill=YELLOW)
put(a, "A15", "Scenario probability")
for j, s in enumerate(["Bear", "Base", "Bull"]):
    put(a, f"{L(2 + j)}15", config.SCENARIO_PROBABILITIES[s], "input", PCT, fill=YELLOW)
put(a, "E15", '=IF(ROUND(SUM(B15:D15),6)=1,"OK: sums to 100%","CHECK: must sum to 100%")')

put(a, "A17", "Target allocation by risk appetite", bold=True)
header(a, 18, ["Asset class", "Low", "Medium", "High"])
for i, k in enumerate(CLASSES, start=19):
    put(a, f"A{i}", k)
    for j, r in enumerate(config.RISK_LEVELS):
        put(a, f"{L(2 + j)}{i}", config.TARGET_ALLOCATION[r][k], "input", PCT, fill=YELLOW)
put(a, "A23", "Total (must be 100%)", bold=True)
for j in range(3):
    col = L(2 + j)
    put(a, f"{col}23", f"=SUM({col}19:{col}22)", fmt=PCT, bold=True)
widths(a, {"A": 40, "B": 14, "C": 14, "D": 14, "E": 26})

# ----------------------------------------------------------- Data sheets
cs = wb.create_sheet("Clients")
header(cs, 1, ["Client ID", "Name", "Risk appetite", "Objective", "Horizon (yrs)"])
for i, r in enumerate(clients.itertuples(), start=2):
    for j, v in enumerate([r.client_id, r.full_name, r.risk_appetite, r.investment_objective, r.investment_horizon_years]):
        put(cs, f"{L(1 + j)}{i}", v, "input")
widths(cs, {"A": 11, "B": 22, "C": 14, "D": 24, "E": 13})

asx = wb.create_sheet("Assets")
header(asx, 1, ["Asset ID", "Symbol", "Asset name", "Class", "Sector", f"Price ₹ ({ds.as_of:%d-%b-%y})"])
for i, r in enumerate(assets.itertuples(), start=2):
    for j, v in enumerate([r.asset_id, r.symbol, r.asset_name, r.asset_class, r.sector]):
        put(asx, f"{L(1 + j)}{i}", v, "input")
    put(asx, f"F{i}", float(ds.latest_prices[r.asset_id]), "input", NUM)
widths(asx, {"A": 10, "B": 16, "C": 30, "D": 13, "E": 20, "F": 18})
A_LAST = NA + 1

hd = wb.create_sheet("Holdings_Data")
header(hd, 1, ["Client ID", "Asset ID", "Quantity", "Avg cost ₹", "Invested ₹", "Current price ₹",
               "Market value ₹", "Profit/Loss ₹", "ROI"])
hs = h.sort_values(["client_id", "asset_id"]).reset_index(drop=True)
for i, r in enumerate(hs.itertuples(), start=2):
    put(hd, f"A{i}", r.client_id, "input"); put(hd, f"B{i}", r.asset_id, "input")
    put(hd, f"C{i}", round(float(r.quantity), 6), "input", QTY)
    put(hd, f"D{i}", round(float(r.avg_cost), 6), "input", NUM)
    put(hd, f"E{i}", f"=C{i}*D{i}", fmt=CUR)
    put(hd, f"F{i}", f"=INDEX(Assets!$F$2:$F${A_LAST},MATCH(B{i},Assets!$A$2:$A${A_LAST},0))", fmt=NUM)
    put(hd, f"G{i}", f"=C{i}*F{i}", fmt=CUR)
    put(hd, f"H{i}", f"=G{i}-E{i}", fmt=CUR)
    put(hd, f"I{i}", f"=IFERROR(H{i}/E{i},0)", fmt=PCT)
widths(hd, {"A": 10, "B": 10, "C": 13, "D": 12, "E": 15, "F": 15, "G": 16, "H": 15, "I": 9})
H_LAST = NH + 1
HR = lambda col: f"Holdings_Data!${col}$2:${col}${H_LAST}"  # noqa: E731

# --------------------------------------------------------------- Portfolio
p = wb.create_sheet("Portfolio", 1)
title(p, "Portfolio valuation", "Choose a client in B2. Formulas: Value = SUM(qty x price); P&L = Value - Invested; ROI = P&L / Invested.")
put(p, "A2", "Selected client ID", bold=True)
put(p, "B2", CLIENT_DEFAULT, "input", fill=YELLOW, bold=True)
dvc = DataValidation(type="list", formula1=f"=Clients!$A$2:$A${NC + 1}", allow_blank=False)
p.add_data_validation(dvc); dvc.add("B2")
put(p, "A3", "Client name"); put(p, "B3", f"=INDEX(Clients!$B$2:$B${NC + 1},MATCH($B$2,Clients!$A$2:$A${NC + 1},0))")
put(p, "A4", "Risk appetite"); put(p, "B4", f"=INDEX(Clients!$C$2:$C${NC + 1},MATCH($B$2,Clients!$A$2:$A${NC + 1},0))")
put(p, "A5", "Objective"); put(p, "B5", f"=INDEX(Clients!$D$2:$D${NC + 1},MATCH($B$2,Clients!$A$2:$A${NC + 1},0))")

PA0 = 24                       # per-asset table first data row
PA1 = PA0 + NA - 1
PT = PA1 + 1
put(p, "A7", "Key figures", bold=True)
put(p, "A8", "Invested amount"); put(p, "B8", f"=E{PT}", fmt=CUR)
put(p, "A9", "Current portfolio value"); put(p, "B9", f"=F{PT}", fmt=CUR)
put(p, "A10", "Profit / Loss"); put(p, "B10", "=B9-B8", fmt=CUR)
put(p, "A11", "ROI"); put(p, "B11", "=IFERROR(B10/B8,0)", fmt=PCT2)
put(p, "A12", "Weighted return check"); put(p, "B12", f"=IFERROR(SUMPRODUCT(E{PA0}:E{PA1},H{PA0}:H{PA1})/E{PT},0)", fmt=PCT2)
put(p, "C12", "Sum of (invested weight x asset ROI); must equal ROI", "label")

put(p, "A14", "Asset-class allocation", bold=True)
header(p, 15, ["Asset class", "Invested ₹", "Value ₹", "Profit/Loss ₹", "ROI", "Weight"])
for i, k in enumerate(CLASSES, start=16):
    put(p, f"A{i}", k)
    put(p, f"B{i}", f"=SUMIFS($E${PA0}:$E${PA1},$C${PA0}:$C${PA1},$A{i})", fmt=CUR)
    put(p, f"C{i}", f"=SUMIFS($F${PA0}:$F${PA1},$C${PA0}:$C${PA1},$A{i})", fmt=CUR)
    put(p, f"D{i}", f"=C{i}-B{i}", fmt=CUR)
    put(p, f"E{i}", f"=IFERROR(D{i}/B{i},0)", fmt=PCT)
    put(p, f"F{i}", f"=IFERROR(C{i}/C$20,0)", fmt=PCT)
put(p, "A20", "Total", bold=True)
for col in "BCD":
    put(p, f"{col}20", f"=SUM({col}16:{col}19)", fmt=CUR, bold=True)
put(p, "E20", "=IFERROR(D20/B20,0)", fmt=PCT, bold=True); put(p, "F20", "=SUM(F16:F19)", fmt=PCT, bold=True)

put(p, "A22", "Holdings by asset (selected client)", bold=True)
header(p, PA0 - 1, ["Asset ID", "Asset name", "Class", "Quantity", "Invested ₹", "Value ₹", "Profit/Loss ₹", "ROI", "Weight"])
for i in range(NA):
    r = PA0 + i
    put(p, f"A{r}", f"=Assets!A{i + 2}"); put(p, f"B{r}", f"=Assets!C{i + 2}"); put(p, f"C{r}", f"=Assets!D{i + 2}")
    crit = f'{HR("A")},$B$2,{HR("B")},$A{r}'
    put(p, f"D{r}", f"=SUMIFS({HR('C')},{crit})", fmt=QTY)
    put(p, f"E{r}", f"=SUMIFS({HR('E')},{crit})", fmt=CUR)
    put(p, f"F{r}", f"=SUMIFS({HR('G')},{crit})", fmt=CUR)
    put(p, f"G{r}", f"=F{r}-E{r}", fmt=CUR)
    put(p, f"H{r}", f"=IFERROR(G{r}/E{r},0)", fmt=PCT)
    put(p, f"I{r}", f"=IFERROR(F{r}/F${PT},0)", fmt=PCT)
put(p, f"A{PT}", "Total", bold=True)
for col in "EFG":
    put(p, f"{col}{PT}", f"=SUM({col}{PA0}:{col}{PA1})", fmt=CUR, bold=True)
put(p, f"H{PT}", f"=IFERROR(G{PT}/E{PT},0)", fmt=PCT, bold=True); put(p, f"I{PT}", f"=SUM(I{PA0}:I{PA1})", fmt=PCT, bold=True)
widths(p, {"A": 24, "B": 30, "C": 14, "D": 14, "E": 16, "F": 16, "G": 16, "H": 10, "I": 10})
pie = PieChart(); pie.title = "Allocation by asset class"; pie.height, pie.width = 7.5, 10
pie.add_data(Reference(p, min_col=3, min_row=15, max_row=19), titles_from_data=True)
pie.set_categories(Reference(p, min_col=1, min_row=16, max_row=19))
p.add_chart(pie, "K3")

# -------------------------------------------------------------- Formulas
f = wb.create_sheet("Formulas")
title(f, "Core formulas - worked example from the brief", "Edit the blue cells; the example reproduces Rs 5,00,000 -> Rs 5,75,000 (ROI 15%).")
put(f, "A4", "Initial investment (₹)"); put(f, "B4", 500000, "input", CUR, fill=YELLOW)
put(f, "A5", "Ending value (₹)"); put(f, "B5", 575000, "input", CUR, fill=YELLOW)
put(f, "A6", "Years held (n)"); put(f, "B6", 1, "input", "0.0", fill=YELLOW)
put(f, "A8", "Profit / Loss = Current - Invested"); put(f, "B8", "=B5-B4", fmt=CUR)
put(f, "A9", "ROI = Profit / Invested"); put(f, "B9", "=IFERROR(B8/B4,0)", fmt=PCT2)
put(f, "A10", "CAGR = (Ending/Beginning)^(1/n) - 1"); put(f, "B10", "=IFERROR((B5/B4)^(1/B6)-1,0)", fmt=PCT2)
put(f, "A12", "Portfolio value = SUM(quantity x current price): see Portfolio sheet", "label")
put(f, "A13", "Portfolio return = SUM(weight x asset return): see Portfolio!B12", "label")
put(f, "A14", "Volatility, Sharpe, Beta, Max drawdown: see Risk_Returns sheet", "label")
widths(f, {"A": 48, "B": 18})

# ------------------------------------------------------------- Scenarios
s = wb.create_sheet("Scenarios")
title(s, "Scenario analysis", "Expected return = SUMPRODUCT(class weights x scenario class returns). Contributions added at each year end.")
put(s, "A3", "Portfolio value today"); put(s, "B3", "=Portfolio!B9", fmt=CUR)
header(s, 5, ["Asset class", "Weight"])
for i, k in enumerate(CLASSES, start=6):
    put(s, f"A{i}", k); put(s, f"B{i}", f"=Portfolio!F{i + 10}", fmt=PCT)
header(s, 11, ["", "Bear", "Base", "Bull"])
put(s, "A12", "Expected annual return", bold=True)
for j in range(3):
    col = L(2 + j)
    put(s, f"{col}12", f"=SUMPRODUCT($B$6:$B$9,Assumptions!{col}$11:{col}$14)", fmt=PCT2)
header(s, 15, ["Year", "Bear", "Base", "Bull"])
for y in range(11):
    r = 16 + y
    put(s, f"A{r}", y, "label", "0")
    for j in range(3):
        col = L(2 + j)
        put(s, f"{col}{r}", "=$B$3" if y == 0 else f"={col}{r - 1}*(1+{col}$12)+Assumptions!$B$6", fmt=CUR)
put(s, "A28", "Value at horizon", bold=True)
put(s, "A29", "Capital contributed")
put(s, "A30", "Gain vs contributed")
put(s, "A31", "Probability")
put(s, "A32", "Probability-weighted value at horizon", bold=True)
for j in range(3):
    col = L(2 + j)
    put(s, f"{col}28", f"=INDEX({col}16:{col}26,Assumptions!$B$5+1)", fmt=CUR, bold=True)
    put(s, f"{col}29", "=$B$3+Assumptions!$B$6*Assumptions!$B$5", fmt=CUR)
    put(s, f"{col}30", f"={col}28-{col}29", fmt=CUR)
    put(s, f"{col}31", f"=Assumptions!{col}15", fmt=PCT)
put(s, "B32", "=SUMPRODUCT(B28:D28,B31:D31)", fmt=CUR, bold=True)
widths(s, {"A": 38, "B": 17, "C": 17, "D": 17})
lc = LineChart(); lc.title = "Projected portfolio value"; lc.height, lc.width = 8, 14
lc.add_data(Reference(s, min_col=2, max_col=4, min_row=15, max_row=26), titles_from_data=True)
lc.set_categories(Reference(s, min_col=1, min_row=16, max_row=26))
s.add_chart(lc, "F3")

# ----------------------------------------------------------- Rebalancing
rb = wb.create_sheet("Rebalancing")
title(rb, "Portfolio rebalancing analysis", "Trade = target value - current value (positive = buy, negative = sell).")
put(rb, "A3", "Client"); put(rb, "B3", "=Portfolio!B2")
put(rb, "A4", "Risk appetite"); put(rb, "B4", "=Portfolio!B4")
put(rb, "A5", "New cash to invest (₹)"); put(rb, "B5", 0, "input", CUR, fill=YELLOW)
put(rb, "A6", "Drift threshold"); put(rb, "B6", "=Assumptions!B4", fmt=PCT)
header(rb, 8, ["Asset class", "Current ₹", "Current weight", "Target weight", "Drift (pp)", "Target ₹", "Trade ₹", "Action"])
for i, k in enumerate(CLASSES, start=9):
    put(rb, f"A{i}", k)
    put(rb, f"B{i}", f"=Portfolio!C{i + 7}", fmt=CUR)
    put(rb, f"C{i}", f"=IFERROR(B{i}/B$13,0)", fmt=PCT)
    put(rb, f"D{i}", f"=INDEX(Assumptions!$B$19:$D$22,MATCH($A{i},Assumptions!$A$19:$A$22,0),MATCH($B$4,Assumptions!$B$18:$D$18,0))", fmt=PCT)
    put(rb, f"E{i}", f"=C{i}-D{i}", fmt=PCT)
    put(rb, f"F{i}", f"=D{i}*(B$13+$B$5)", fmt=CUR)
    put(rb, f"G{i}", f"=F{i}-B{i}", fmt=CUR)
    put(rb, f"H{i}", f'=IF(ABS(E{i})<$B$6,"Hold",IF(G{i}>0,"Buy","Sell"))')
put(rb, "A13", "Total", bold=True)
for col in "BCDFG":
    put(rb, f"{col}13", f"=SUM({col}9:{col}12)", fmt=PCT if col in "CD" else CUR, bold=True)
put(rb, "A15", "Rebalancing needed?", bold=True)
put(rb, "B15", '=IF(COUNTIF(H9:H12,"Hold")=4,"No - within threshold","Yes - see actions")', bold=True)
widths(rb, {"A": 24, "B": 16, "C": 15, "D": 15, "E": 12, "F": 16, "G": 16, "H": 10})

# ---------------------------------------------------------- Prices monthly
pm = ds.prices.resample("ME").last()
bm = ds.benchmark.resample("ME").last()
NM = len(pm)
pmw = wb.create_sheet("Prices_Monthly")
put(pmw, "A1", "Month-end prices (₹) from the SQL database. Row 3 = units held by the client selected on Portfolio.", bold=True)
header(pmw, 2, ["Month-end"] + list(pm.columns) + [config.BENCHMARK_CODE])
put(pmw, "A3", "Qty held (selected client)", bold=True)
last_col = L(1 + NA)
for j, aid in enumerate(pm.columns):
    col = L(2 + j)
    put(pmw, f"{col}3", f"=SUMIFS({HR('C')},{HR('A')},Portfolio!$B$2,{HR('B')},{col}$2)", fmt=QTY)
for i, (d, row) in enumerate(pm.iterrows(), start=4):
    put(pmw, f"A{i}", d.to_pydatetime(), "input", DATE)
    for j, aid in enumerate(pm.columns):
        put(pmw, f"{L(2 + j)}{i}", float(row[aid]), "input", NUM)
    put(pmw, f"{L(2 + NA)}{i}", float(bm.loc[d]), "input", NUM)
pmw.freeze_panes = "B4"
widths(pmw, {"A": 26})
PM_LAST = 3 + NM

# ----------------------------------------------------------- Risk_Returns
rr = wb.create_sheet("Risk_Returns")
title(rr, "Risk & return (static back-test of current holdings, month-end)", "See Guide for method notes.")
header(rr, 4, ["Month-end", "Portfolio value ₹", "Portfolio return", "Benchmark level", "Benchmark return", "Running peak ₹", "Drawdown"])
R0 = 5
for k in range(NM):
    r, src = R0 + k, 4 + k
    put(rr, f"A{r}", f"=Prices_Monthly!A{src}", fmt=DATE)
    put(rr, f"B{r}", f"=SUMPRODUCT(Prices_Monthly!$B$3:${last_col}$3,Prices_Monthly!B{src}:{last_col}{src})", fmt=CUR)
    put(rr, f"D{r}", f"=Prices_Monthly!{L(2 + NA)}{src}", fmt=NUM)
    if k > 0:
        put(rr, f"C{r}", f"=IF(B{r - 1}>0,B{r}/B{r - 1}-1,0)", fmt=PCT2)
        put(rr, f"E{r}", f"=D{r}/D{r - 1}-1", fmt=PCT2)
    put(rr, f"F{r}", f"=MAX(B${R0}:B{r})", fmt=CUR)
    put(rr, f"G{r}", f"=IF(F{r}>0,B{r}/F{r}-1,0)", fmt=PCT2)
R1 = R0 + NM - 1
C_ = f"C{R0 + 1}:C{R1}"; E_ = f"E{R0 + 1}:E{R1}"
header(rr, 4, ["Metric", "Value"], col=9)
stats = [
    ("Months of returns", f"=COUNT({C_})", "0"),
    ("Average monthly return", f"=AVERAGE({C_})", PCT2),
    ("Annualised return (geometric)", f"=IFERROR((B{R1}/B{R0})^(12/COUNT({C_}))-1,0)", PCT2),
    ("Annualised volatility = STDEV x SQRT(12)", f"=STDEV({C_})*SQRT(12)", PCT2),
    ("Risk-free rate", "=Assumptions!B3", PCT2),
    ("Sharpe ratio", "=IFERROR((J7-J9)/J8,0)", "0.00"),
    ("Beta = COVAR / VARP (benchmark)", f"=IFERROR(COVAR({C_},{E_})/VARP({E_}),0)", "0.00"),
    ("Beta cross-check (SLOPE)", f"=IFERROR(SLOPE({C_},{E_}),0)", "0.00"),
    ("Maximum drawdown", f"=MIN(G{R0}:G{R1})", PCT2),
    ("Risk classification", '=IF(J8<Assumptions!B7,"Low",IF(J8<Assumptions!B8,"Medium","High"))', None),
    ("Client risk appetite", "=Portfolio!B4", None),
]
for i, (lab, fm, nf) in enumerate(stats, start=5):
    put(rr, f"I{i}", lab); put(rr, f"J{i}", fm, fmt=nf, bold=True)
widths(rr, {"A": 12, "B": 18, "C": 14, "D": 15, "E": 15, "F": 16, "G": 11, "H": 3, "I": 40, "J": 14})
rr.freeze_panes = "A5"
ch = LineChart(); ch.title = "Portfolio value (back-test)"; ch.height, ch.width = 8, 16
ch.add_data(Reference(rr, min_col=2, min_row=4, max_row=R1), titles_from_data=True)
ch.set_categories(Reference(rr, min_col=1, min_row=R0, max_row=R1))
rr.add_chart(ch, "I18")

wb.save(OUT)
print("saved", OUT, f"({NH} holdings rows, {NM} month-ends)")
