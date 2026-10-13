"""
Builds the KPI tables used by the Tableau dashboard:
  kpi_daily_summary.csv    - volume, revenue, fail rate, refund rate per day
  kpi_merchant_segment.csv - revenue and take rate per segment
  kpi_weekly_snapshot.csv  - last 7 days vs the 7 before (also used by ai_narrative.py)
"""

import os
import sqlite3
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "finance_ops.db")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")


def load_tables(conn):
    txns = pd.read_sql("SELECT * FROM transactions", conn, parse_dates=["txn_date"])
    settlements = pd.read_sql("SELECT * FROM settlements", conn, parse_dates=["settlement_date"])
    refunds = pd.read_sql("SELECT * FROM refunds", conn, parse_dates=["refund_date"])
    merchants = pd.read_sql("SELECT * FROM merchants", conn)
    return txns, settlements, refunds, merchants


def build_daily_summary(txns, settlements, refunds):
    daily_volume = txns.groupby(txns["txn_date"].dt.date).agg(
        total_transactions=("txn_id", "count"),
        successful_transactions=("status", lambda s: (s == "success").sum()),
        failed_transactions=("status", lambda s: (s == "failed").sum()),
        gross_amount=("amount", lambda a: a[a > 0].sum()),
    )

    settled = settlements.merge(txns[["txn_id", "txn_date"]], on="txn_id")
    daily_revenue = settled.groupby(settled["txn_date"].dt.date).agg(
        net_settled_amount=("settled_amount", "sum"),
        total_fees_earned=("fee", "sum"),
    )

    daily_refunds = refunds.merge(txns[["txn_id", "txn_date"]], on="txn_id", how="left")
    daily_refund_amt = daily_refunds.groupby(daily_refunds["txn_date"].dt.date).agg(
        refund_amount=("refund_amount", "sum"),
        refund_count=("refund_id", "count"),
    )

    daily = daily_volume.join(daily_revenue, how="left").join(daily_refund_amt, how="left").fillna(0)
    daily["failed_txn_rate_pct"] = round(
        100 * daily["failed_transactions"] / daily["total_transactions"], 2
    )
    daily["refund_rate_pct"] = round(
        100 * daily["refund_count"] / daily["successful_transactions"].replace(0, pd.NA), 2
    ).fillna(0)
    daily.index.name = "date"
    return daily.reset_index().sort_values("date")


def build_segment_summary(txns, settlements, merchants):
    txn_merch = txns.merge(merchants[["merchant_id", "segment"]], on="merchant_id")
    settled_merch = settlements.merge(txns[["txn_id", "merchant_id"]], on="txn_id").merge(
        merchants[["merchant_id", "segment"]], on="merchant_id"
    )

    volume = txn_merch[txn_merch["status"] == "success"].groupby("segment").agg(
        successful_transactions=("txn_id", "count"),
        gross_amount=("amount", "sum"),
    )
    revenue = settled_merch.groupby("segment").agg(
        net_settled_amount=("settled_amount", "sum"),
        total_fees_earned=("fee", "sum"),
    )

    seg = volume.join(revenue, how="left").fillna(0)
    seg["effective_take_rate_pct"] = round(100 * seg["total_fees_earned"] / seg["gross_amount"], 3)
    return seg.reset_index().sort_values("gross_amount", ascending=False)


def build_weekly_snapshot(daily_df):
    daily_df = daily_df.copy()
    daily_df["date"] = pd.to_datetime(daily_df["date"])
    last_date = daily_df["date"].max()
    this_week_start = last_date - pd.Timedelta(days=6)
    prior_week_start = this_week_start - pd.Timedelta(days=7)

    this_week = daily_df[daily_df["date"] > this_week_start]
    prior_week = daily_df[(daily_df["date"] > prior_week_start) & (daily_df["date"] <= this_week_start)]

    def agg(week_df):
        return {
            "total_transactions": int(week_df["total_transactions"].sum()),
            "gross_amount": round(week_df["gross_amount"].sum(), 2),
            "net_settled_amount": round(week_df["net_settled_amount"].sum(), 2),
            "total_fees_earned": round(week_df["total_fees_earned"].sum(), 2),
            "refund_amount": round(week_df["refund_amount"].sum(), 2),
            "avg_failed_txn_rate_pct": round(week_df["failed_txn_rate_pct"].mean(), 2),
            "avg_refund_rate_pct": round(week_df["refund_rate_pct"].mean(), 2),
        }

    this_agg = agg(this_week)
    prior_agg = agg(prior_week)

    snapshot = []
    for key in this_agg:
        cur, prev = this_agg[key], prior_agg[key]
        wow_pct = round(100 * (cur - prev) / prev, 2) if prev else None
        snapshot.append({"metric": key, "this_week": cur, "prior_week": prev, "wow_change_pct": wow_pct})

    return pd.DataFrame(snapshot)


def main():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    txns, settlements, refunds, merchants = load_tables(conn)
    conn.close()

    daily = build_daily_summary(txns, settlements, refunds)
    daily.to_csv(os.path.join(REPORTS_DIR, "kpi_daily_summary.csv"), index=False)

    segment = build_segment_summary(txns, settlements, merchants)
    segment.to_csv(os.path.join(REPORTS_DIR, "kpi_merchant_segment.csv"), index=False)

    weekly = build_weekly_snapshot(daily)
    weekly.to_csv(os.path.join(REPORTS_DIR, "kpi_weekly_snapshot.csv"), index=False)

    print("KPI reports written:")
    print(f"  {os.path.join(REPORTS_DIR, 'kpi_daily_summary.csv')}  ({len(daily)} days)")
    print(f"  {os.path.join(REPORTS_DIR, 'kpi_merchant_segment.csv')}  ({len(segment)} segments)")
    print(f"  {os.path.join(REPORTS_DIR, 'kpi_weekly_snapshot.csv')}")
    print("\nWeekly snapshot (this week vs prior week):")
    print(weekly.to_string(index=False))


if __name__ == "__main__":
    main()
