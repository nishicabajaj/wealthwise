"""Thin database layer: SQLite by default, MySQL when WEALTHWISE_DB_URL is set.

    export WEALTHWISE_DB_URL="mysql+pymysql://user:pass@localhost:3306/wealthwise"

All write SQL in the app uses :named parameters, which both backends accept.
"""
from __future__ import annotations

import os
import sqlite3

import pandas as pd

from . import config


def _statements(script: str) -> list[str]:
    lines = [ln for ln in script.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def connect(url: str | None = None):
    """Return a DB connection. url: sqlite:///path | mysql+pymysql://..."""
    url = url or os.getenv("WEALTHWISE_DB_URL") or f"sqlite:///{config.DB_PATH}"
    if url.startswith("sqlite"):
        path = url.split("sqlite:///", 1)[1]
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    from sqlalchemy import create_engine  # imported lazily: only needed for MySQL
    return create_engine(url, pool_pre_ping=True).connect()


def dialect(conn) -> str:
    return "sqlite" if isinstance(conn, sqlite3.Connection) else "mysql"


def run_script(conn, script: str) -> None:
    if dialect(conn) == "sqlite":
        for stmt in _statements(script):
            conn.execute(stmt)
        conn.commit()
    else:
        from sqlalchemy import text
        for stmt in _statements(script):
            conn.execute(text(stmt))
        conn.commit()


def init_schema(conn, drop_existing: bool = False) -> None:
    if drop_existing:
        for v in ("v_client_portfolio", "v_holdings", "v_positions", "v_latest_price"):
            run_script(conn, f"DROP VIEW IF EXISTS {v}")
        for t in ("transactions", "prices", "benchmark_prices", "assets", "clients"):
            run_script(conn, f"DROP TABLE IF EXISTS {t}")
    schema = "schema_sqlite.sql" if dialect(conn) == "sqlite" else "schema_mysql.sql"
    run_script(conn, (config.SQL_DIR / schema).read_text(encoding="utf-8"))
    run_script(conn, (config.SQL_DIR / "views.sql").read_text(encoding="utf-8"))


def execute(conn, sql: str, params: dict | None = None):
    """Run one write statement with :named params; returns lastrowid if available."""
    if dialect(conn) == "sqlite":
        cur = conn.execute(sql, params or {})
        conn.commit()
        return cur.lastrowid
    from sqlalchemy import text
    res = conn.execute(text(sql), params or {})
    conn.commit()
    return res.lastrowid


def read(conn, sql: str) -> pd.DataFrame:
    return pd.read_sql_query(sql, conn)


def write_frame(conn, table: str, df: pd.DataFrame) -> None:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")
    out.to_sql(table, conn, if_exists="append", index=False, chunksize=5000)
    conn.commit()
