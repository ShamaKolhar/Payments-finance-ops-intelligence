-- Data quality checks, one view per check.
-- SQLite syntax (julianday etc.), run from src/data_validation.py

-- 1. duplicates: same merchant, date, amount and method
DROP VIEW IF EXISTS vw_duplicate_transactions;
CREATE VIEW vw_duplicate_transactions AS
SELECT merchant_id, txn_date, amount, payment_method, COUNT(*) AS occurrences,
       GROUP_CONCAT(txn_id) AS txn_ids
FROM transactions
GROUP BY merchant_id, txn_date, amount, payment_method
HAVING COUNT(*) > 1;

-- 2. successful txns with no settlement
DROP VIEW IF EXISTS vw_missing_settlements;
CREATE VIEW vw_missing_settlements AS
SELECT t.txn_id, t.merchant_id, t.txn_date, t.amount
FROM transactions t
LEFT JOIN settlements s ON t.txn_id = s.txn_id
WHERE t.status = 'success' AND s.settlement_id IS NULL;

-- 3. settled_amount should be amount - fee (allowing Rs 1 for rounding)
DROP VIEW IF EXISTS vw_settlement_mismatches;
CREATE VIEW vw_settlement_mismatches AS
SELECT s.settlement_id, s.txn_id, t.amount AS txn_amount, s.fee,
       s.settled_amount, ROUND(t.amount - s.fee, 2) AS expected_settled_amount,
       ROUND(s.settled_amount - (t.amount - s.fee), 2) AS discrepancy
FROM settlements s
JOIN transactions t ON s.txn_id = t.txn_id
WHERE ABS(s.settled_amount - (t.amount - s.fee)) > 1.0;

-- 4. late settlements: more than 3 days after txn
-- TODO: this is calendar days, so weekend settlements get flagged too
DROP VIEW IF EXISTS vw_late_settlements;
CREATE VIEW vw_late_settlements AS
SELECT s.settlement_id, s.txn_id, t.txn_date, s.settlement_date,
       julianday(s.settlement_date) - julianday(t.txn_date) AS days_to_settle
FROM settlements s
JOIN transactions t ON s.txn_id = t.txn_id
WHERE julianday(s.settlement_date) - julianday(t.txn_date) > 3;

-- 5. refunds pointing to a txn that doesn't exist
DROP VIEW IF EXISTS vw_orphan_refunds;
CREATE VIEW vw_orphan_refunds AS
SELECT r.refund_id, r.txn_id, r.refund_date, r.refund_amount
FROM refunds r
LEFT JOIN transactions t ON r.txn_id = t.txn_id
WHERE t.txn_id IS NULL;

-- 6. zero or negative amounts
DROP VIEW IF EXISTS vw_invalid_amounts;
CREATE VIEW vw_invalid_amounts AS
SELECT txn_id, merchant_id, txn_date, amount
FROM transactions
WHERE amount <= 0;
