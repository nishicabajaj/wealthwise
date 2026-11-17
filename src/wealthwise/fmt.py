"""Indian-style number formatting (lakh / crore grouping)."""
from __future__ import annotations

import math


def inr(x, symbol: str = "₹", decimals: int = 0) -> str:
    """Format a number with Indian digit grouping: 1234567 -> ₹12,34,567."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    neg = x < 0
    s = f"{abs(float(x)):.{decimals}f}"
    whole, _, frac = s.partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    out = f"{symbol}{whole}" + (f".{frac}" if frac else "")
    return f"-{out}" if neg else out


def inr_short(x, symbol: str = "₹") -> str:
    """Compact form: ₹1.25 Cr, ₹4.50 L, ₹8,500."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    sign = "-" if x < 0 else ""
    a = abs(float(x))
    if a >= 1e7:
        return f"{sign}{symbol}{a / 1e7:.2f} Cr"
    if a >= 1e5:
        return f"{sign}{symbol}{a / 1e5:.2f} L"
    return f"{sign}{symbol}{a:,.0f}"


def pct(x, decimals: int = 2) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "–"
    return f"{x * 100:.{decimals}f}%"
