"""Create the database, load synthetic data and export CSV copies.

    python scripts/build_db.py                 # SQLite at data/wealthwise.db
    WEALTHWISE_DB_URL=mysql+pymysql://user:pw@localhost/wealthwise python scripts/build_db.py
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wealthwise import config, data_gen, db  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-csv", action="store_true", help="skip CSV export to data/csv")
    args = ap.parse_args()

    frames = data_gen.generate_all(args.seed)
    conn = db.connect()
    db.init_schema(conn, drop_existing=True)
    for table in ("clients", "assets", "prices", "benchmark_prices", "transactions"):
        db.write_frame(conn, table, frames[table])
        print(f"loaded {table:<17} {len(frames[table]):>7,} rows")
    if not args.no_csv:
        out = config.DATA_DIR / "csv"
        out.mkdir(parents=True, exist_ok=True)
        for name, df in frames.items():
            df.to_csv(out / f"{name}.csv", index=False)
        print(f"CSV copies written to {out}")


if __name__ == "__main__":
    main()
