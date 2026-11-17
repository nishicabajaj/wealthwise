"""Offline smoke test of app/streamlit_app.py using stand-in streamlit/plotly modules.

Executes every page's Python logic (data prep, column names, unpacking, formatting).
It does NOT render anything - run the real app with `streamlit run` for that.
"""
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["Dashboard", "Client portfolio", "Risk analysis", "Benchmark comparison",
         "Scenarios & rebalancing", "Manage data", "Reports"]


def make_streamlit(page):
    st = MagicMock(name="streamlit")
    st.session_state = {}
    st.sidebar.radio.return_value = page
    st.sidebar.number_input.side_effect = lambda label, mn, mx, val, *a, **k: val
    st.columns.side_effect = lambda spec, **k: [st] * (spec if isinstance(spec, int) else len(spec))
    st.tabs.side_effect = lambda names: [st] * len(names)
    st.selectbox.side_effect = lambda label, opts, *a, **k: list(opts)[0]
    st.radio.side_effect = lambda label, opts, *a, **k: list(opts)[0]
    st.slider.side_effect = lambda label, mn, mx, val=None, *a, **k: val if val is not None else mn
    st.number_input.side_effect = lambda label, mn=None, mx=None, val=None, *a, **k: val if val is not None else mn
    st.button.return_value = True
    st.stop.side_effect = SystemExit
    st.rerun.side_effect = SystemExit
    st.cache_data = lambda *a, **k: (a[0] if a and callable(a[0]) else (lambda f: f))
    st.cache_data.clear = lambda: None
    st.cache_data = type("CD", (), {"__call__": lambda self, *a, **k: (a[0] if a and callable(a[0]) else (lambda f: f)),
                                    "clear": staticmethod(lambda: None)})()
    st.form_submit_button.return_value = False
    for n in ('form',):
        getattr(st, n).return_value = st
    st.__enter__ = lambda s: s
    st.__exit__ = lambda *a: False
    st.date_input.side_effect = lambda label, val=None, *a, **k: pd.Timestamp(val)
    return st


def run(page):
    sys.modules["streamlit"] = make_streamlit(page)
    for name in ("plotly", "plotly.express", "plotly.graph_objects"):
        sys.modules[name] = MagicMock()
    sys.modules.pop("charts", None)
    src = (ROOT / "app" / "streamlit_app.py").read_text()
    sys.argv = ["app"]
    try:
        exec(compile(src, "streamlit_app.py", "exec"), {"__name__": "__main__", "__file__": str(ROOT / "app" / "streamlit_app.py")})
    except SystemExit:
        pass


if __name__ == "__main__":
    import os, shutil, tempfile
    tmp = Path(tempfile.mkdtemp()) / "smoke.db"
    shutil.copy(ROOT / "data" / "wealthwise.db", tmp)
    os.environ["WEALTHWISE_DB_URL"] = f"sqlite:///{tmp}"   # never touch the real DB
    for p in PAGES:
        run(p)
        print("ok  ", p)
