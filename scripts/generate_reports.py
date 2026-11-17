"""Write a PDF per client plus the firm report to outputs/reports/."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wealthwise import config, db, reports, store  # noqa: E402

ds = store.load_dataset(db.connect())
out = config.OUTPUT_DIR / "reports"
out.mkdir(parents=True, exist_ok=True)
(out / "firm_report.pdf").write_bytes(reports.firm_report_pdf(ds))
for cid in ds.clients["client_id"]:
    (out / f"{cid}_report.pdf").write_bytes(reports.client_report_pdf(ds, cid))
print(f"wrote {len(ds.clients) + 1} reports to {out}")
