"""
Generates the synthetic dataset (merchants, transactions, settlements,
refunds) and saves it to data/raw/*.csv and data/finance_ops.db.

Some bad records are added on purpose so the validation step has
something to catch: duplicates, missing settlements, amount mismatches,
late settlements, orphan refunds and negative amounts.
"""

import os
import random
import sqlite3
import datetime as dt

import numpy as np
import pandas as pd

random.seed(42)
np.random.seed(42)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "raw")
DB_PATH = os.path.join(BASE_DIR, "finance_ops.db")

os.makedirs(RAW_DIR, exist_ok=True)

START_DATE = dt.date(2026, 6, 1)
END_DATE = dt.date(2026, 8, 31)
N_MERCHANTS = 60
N_TRANSACTIONS = 12000

SEGMENTS = ["D2C E-commerce", "SaaS", "Travel", "Food Delivery", "EdTech", "Marketplace"]
CITIES = ["Bengaluru", "Mumbai", "Delhi NCR", "Hyderabad", "Pune", "Chennai"]
PAYMENT_METHODS = ["UPI", "Card", "Netbanking", "Wallet", "EMI"]
REFUND_REASONS = ["Customer request", "Duplicate charge", "Order cancelled", "Product issue", "Fraud check"]


def random_date(start, end):
    delta = (end - start).days
    return start + dt.timedelta(days=random.randint(0, delta))


def business_days_after(d, n):
    cur = d
    added = 0
    while added < n:
        cur += dt.timedelta(days=1)
        if cur.weekday() < 5:
            added += 1
    return cur


def generate_merchants():
    rows = []
    for i in range(1, N_MERCHANTS + 1):
        onboarding = random_date(dt.date(2024, 1, 1), dt.date(2026, 5, 1))
        rows.append({
            "merchant_id": f"M{i:04d}",
            "merchant_name": f"Merchant_{i:04d}",
            "segment": random.choice(SEGMENTS),
            "city": random.choice(CITIES),
            "onboarding_date": onboarding.isoformat(),
        })
    return pd.DataFrame(rows)


def generate_transactions(merchants_df):
    rows = []
    merchant_ids = merchants_df["merchant_id"].tolist()
    # a few merchants get most of the volume
    weights = np.random.pareto(2.0, size=len(merchant_ids)) + 0.1
    weights = weights / weights.sum()

    for i in range(1, N_TRANSACTIONS + 1):
        merchant_id = np.random.choice(merchant_ids, p=weights)
        txn_date = random_date(START_DATE, END_DATE)
        amount = round(np.random.lognormal(mean=7.2, sigma=1.0), 2)
        status = np.random.choice(
            ["success", "failed", "pending"], p=[0.90, 0.07, 0.03]
        )
        rows.append({
            "txn_id": f"T{i:07d}",
            "merchant_id": merchant_id,
            "txn_date": txn_date.isoformat(),
            "amount": amount,
            "payment_method": random.choice(PAYMENT_METHODS),
            "status": status,
        })

    df = pd.DataFrame(rows)

    # duplicates (~0.5%), same txn with a new id
    dupes = df.sample(frac=0.005, random_state=1).copy()
    dupes["txn_id"] = dupes["txn_id"] + "_DUP"
    df = pd.concat([df, dupes], ignore_index=True)

    # negative amounts (~0.2%)
    bad_idx = df.sample(frac=0.002, random_state=2).index
    df.loc[bad_idx, "amount"] = df.loc[bad_idx, "amount"] * -1

    return df


def generate_settlements(transactions_df):
    rows = []
    successful = transactions_df[transactions_df["status"] == "success"].copy()

    # ~2% of successful txns get no settlement
    missing_mask = np.random.rand(len(successful)) < 0.02
    to_settle = successful[~missing_mask]

    settlement_id = 1
    for _, txn in to_settle.iterrows():
        txn_date = dt.date.fromisoformat(txn["txn_date"])
        fee = round(txn["amount"] * 0.021, 2)
        settled_amount = round(txn["amount"] - fee, 2)

        # normally T+1 or T+2
        settlement_date = business_days_after(txn_date, random.choice([1, 1, 2]))

        # ~3% settle late (5-10 business days)
        is_late = random.random() < 0.03
        if is_late:
            settlement_date = business_days_after(txn_date, random.randint(5, 10))

        # ~1.5% settled amount is off
        is_mismatch = random.random() < 0.015
        if is_mismatch:
            settled_amount = round(settled_amount + random.choice([-50, -20, 15, 40]), 2)

        rows.append({
            "settlement_id": f"S{settlement_id:07d}",
            "txn_id": txn["txn_id"],
            "settlement_date": settlement_date.isoformat(),
            "fee": fee,
            "settled_amount": settled_amount,
            "status": "settled",
        })
        settlement_id += 1

    return pd.DataFrame(rows)


def generate_refunds(transactions_df):
    rows = []
    successful = transactions_df[transactions_df["status"] == "success"]
    refund_candidates = successful.sample(frac=0.04, random_state=3)

    refund_id = 1
    for _, txn in refund_candidates.iterrows():
        txn_date = dt.date.fromisoformat(txn["txn_date"])
        refund_date = business_days_after(txn_date, random.randint(1, 15))
        refund_amount = round(txn["amount"] * random.choice([1.0, 1.0, 0.5]), 2)
        rows.append({
            "refund_id": f"R{refund_id:06d}",
            "txn_id": txn["txn_id"],
            "refund_date": refund_date.isoformat(),
            "refund_amount": refund_amount,
            "reason": random.choice(REFUND_REASONS),
        })
        refund_id += 1

    df = pd.DataFrame(rows)

    # ~1% orphan refunds
    n_orphans = max(1, int(len(df) * 0.01))
    orphan_rows = []
    for i in range(n_orphans):
        refund_id += 1
        orphan_rows.append({
            "refund_id": f"R{refund_id:06d}",
            "txn_id": f"T9{i:06d}",  # no such txn
            "refund_date": random_date(START_DATE, END_DATE).isoformat(),
            "refund_amount": round(random.uniform(200, 3000), 2),
            "reason": random.choice(REFUND_REASONS),
        })
    df = pd.concat([df, pd.DataFrame(orphan_rows)], ignore_index=True)

    return df


def main():
    print("Generating merchants...")
    merchants = generate_merchants()

    print("Generating transactions...")
    transactions = generate_transactions(merchants)

    print("Generating settlements...")
    settlements = generate_settlements(transactions)

    print("Generating refunds...")
    refunds = generate_refunds(transactions)

    merchants.to_csv(os.path.join(RAW_DIR, "merchants.csv"), index=False)
    transactions.to_csv(os.path.join(RAW_DIR, "transactions.csv"), index=False)
    settlements.to_csv(os.path.join(RAW_DIR, "settlements.csv"), index=False)
    refunds.to_csv(os.path.join(RAW_DIR, "refunds.csv"), index=False)

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    merchants.to_sql("merchants", conn, index=False)
    transactions.to_sql("transactions", conn, index=False)
    settlements.to_sql("settlements", conn, index=False)
    refunds.to_sql("refunds", conn, index=False)
    conn.close()

    print("\nDone.")
    print(f"  Merchants:    {len(merchants):,}")
    print(f"  Transactions: {len(transactions):,}")
    print(f"  Settlements:  {len(settlements):,}")
    print(f"  Refunds:      {len(refunds):,}")
    print(f"\nCSV files written to: {RAW_DIR}")
    print(f"SQLite DB written to: {DB_PATH}")


if __name__ == "__main__":
    main()
