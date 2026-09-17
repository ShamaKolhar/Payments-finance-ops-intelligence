-- ============================================================
-- schema.sql
-- Production-style schema (PostgreSQL dialect).
-- The demo pipeline runs on SQLite for portability (no server
-- setup required to review this project), but this is the
-- schema it is modeled on and can be deployed to as-is.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS finance;

CREATE TABLE finance.merchants (
    merchant_id      VARCHAR(10)  PRIMARY KEY,
    merchant_name    VARCHAR(255) NOT NULL,
    segment          VARCHAR(50)  NOT NULL,
    city             VARCHAR(50),
    onboarding_date  DATE         NOT NULL
);

CREATE TABLE finance.transactions (
    txn_id           VARCHAR(15)  PRIMARY KEY,
    merchant_id      VARCHAR(10)  NOT NULL REFERENCES finance.merchants(merchant_id),
    txn_date         DATE         NOT NULL,
    amount           NUMERIC(12,2) NOT NULL,
    payment_method   VARCHAR(20)  NOT NULL,
    status           VARCHAR(10)  NOT NULL CHECK (status IN ('success','failed','pending'))
);

CREATE TABLE finance.settlements (
    settlement_id    VARCHAR(10)  PRIMARY KEY,
    txn_id           VARCHAR(15)  NOT NULL REFERENCES finance.transactions(txn_id),
    settlement_date  DATE         NOT NULL,
    fee              NUMERIC(12,2) NOT NULL,
    settled_amount   NUMERIC(12,2) NOT NULL,
    status           VARCHAR(10)  NOT NULL DEFAULT 'settled'
);

CREATE TABLE finance.refunds (
    refund_id        VARCHAR(10)  PRIMARY KEY,
    txn_id           VARCHAR(15)  NOT NULL,  -- intentionally NOT a hard FK here:
                                              -- orphan refunds are a real-world
                                              -- failure mode this project detects,
                                              -- so the constraint is enforced in
                                              -- the validation layer, not the DDL.
    refund_date      DATE         NOT NULL,
    refund_amount    NUMERIC(12,2) NOT NULL,
    reason           VARCHAR(50)
);

CREATE INDEX idx_txn_merchant_date ON finance.transactions(merchant_id, txn_date);
CREATE INDEX idx_settlement_txn ON finance.settlements(txn_id);
CREATE INDEX idx_refund_txn ON finance.refunds(txn_id);
