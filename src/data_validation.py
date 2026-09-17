"""
data_validation.py
-------------------
Runs the reconciliation/data-quality checks defined in
sql/validation_checks.sql against the finance database and
produces:
  - reports/data_quality_report.csv   (one row per check, with counts + severity)
  - reports/data_quality_details/*.csv (the actual flagged records per check)

This is the "ensuring data accuracy" half of the JD.
"""

import os
import sqlite3
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "finance_ops.db")
SQL_PATH = os.path.join(BASE_DIR, "sql", "validation_checks.sql")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
DETAILS_DIR = os.path.join(REPORTS_DIR, "data_quality_details")

# (view_name, human-readable check name, severity)
CHECKS = [
    ("vw_duplicate_transactions", "Duplicate transactions", "High"),
    ("vw_missing_settlements", "Successful transactions missing a settlement", "High"),
    ("vw_settlement_mismatches", "Settlement amount does not reconcile with fee/amount", "High"),
    ("vw_late_settlements", "Settlement completed > 3 days after transaction (SLA breach)", "Medium"),
    ("vw_orphan_refunds", "Refund references a non-existent transaction", "High"),
    ("vw_invalid_amounts", "Zero or negative transaction amount", "Medium"),
]


def run_validation():
    os.makedirs(DETAILS_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    with open(SQL_PATH, "r") as f:
        conn.executescript(f.read())

    total_txns = pd.read_sql("SELECT COUNT(*) AS n FROM transactions", conn)["n"][0]

    summary_rows = []
    for view_name, description, severity in CHECKS:
        df = pd.read_sql(f"SELECT * FROM {view_name}", conn)
        flagged = len(df)
        pct = round(100 * flagged / total_txns, 3) if total_txns else 0

        detail_path = os.path.join(DETAILS_DIR, f"{view_name}.csv")
        df.to_csv(detail_path, index=False)

        summary_rows.append({
            "check": description,
            "severity": severity,
            "records_flagged": flagged,
            "pct_of_transactions": pct,
            "detail_file": os.path.relpath(detail_path, BASE_DIR),
        })

    conn.close()

    summary_df = pd.DataFrame(summary_rows).sort_values(
        by=["severity", "records_flagged"], ascending=[True, False]
    )
    summary_path = os.path.join(REPORTS_DIR, "data_quality_report.csv")
    summary_df.to_csv(summary_path, index=False)

    return summary_df


if __name__ == "__main__":
    summary = run_validation()
    print("Data Quality Summary")
    print("=" * 70)
    print(summary.to_string(index=False))
    print(f"\nDetail files written to: {DETAILS_DIR}")
    print(f"Summary written to: {os.path.join(REPORTS_DIR, 'data_quality_report.csv')}")
