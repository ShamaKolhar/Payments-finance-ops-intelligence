# Payments Finance Ops Intelligence
### Automated Business Reporting & Data Quality Monitoring Pipeline (with AI-generated commentary)

A finance-ops pipeline for a payments company: it ingests transaction,
settlement, and refund data, catches the data-quality issues that
normally slip past manual review, rolls everything up into
BI-ready business KPI reports, and uses the Claude API to auto-draft
the executive commentary that usually eats an analyst's Monday morning.

Built to mirror the day-to-day of a **Data Analyst, Business Finance**
role at a payments/fintech company: *"supporting the finance team with
data and analysis requirements, process improvements and automations
through AI powered workflows... setting up automated business reports
and ensuring data accuracy."*

---

## What it does

```
data/generate_data.py  →  finance_ops.db  →  src/data_validation.py  →  reports/data_quality_report.csv
                                          →  src/reporting.py          →  reports/kpi_*.csv
                                                                       →  src/ai_narrative.py → reports/ai_narrative_*.md
```

1. **Synthetic payments dataset** — 60 merchants, ~12,000 transactions
   across 3 months, with settlements and refunds, and *deliberately
   injected* real-world data problems (duplicates, missing settlements,
   amount mismatches, late settlements, orphan refunds, bad amounts).
2. **Data accuracy layer** (SQL + Python) — reconciles transactions
   against settlements and refunds, flags every issue by severity, and
   writes both a summary and the underlying bad records.
3. **Automated business reporting** (SQL + Python) — daily KPIs, revenue
   by merchant segment, and a week-over-week snapshot, all as clean
   CSVs ready to plug into Power BI or Tableau.
4. **AI-powered workflow (Claude API)** — turns the KPI snapshot and
   data-quality summary into a short, plain-English executive
   commentary automatically, instead of an analyst writing it by hand
   every week.

## Why it's built this way

Every piece maps directly onto a line in the job description:

| JD requirement | Where it's covered |
|---|---|
| SQL | `sql/schema.sql`, `sql/validation_checks.sql` |
| Python | `data/generate_data.py`, `src/data_validation.py`, `src/reporting.py` |
| Claude / AI tools, AI-powered workflows | `src/ai_narrative.py` |
| Automated business reports | `src/reporting.py` → `reports/kpi_*.csv`, run via `run_pipeline.py` |
| Ensuring data accuracy | `src/data_validation.py` → `reports/data_quality_report.csv` |
| Power BI / Tableau | `docs/dashboard_guide.md` — CSVs designed as direct BI sources |

## Folder structure

```
payments-finance-ops-intelligence/
├── README.md
├── requirements.txt
├── run_pipeline.py              ← run this to execute everything
├── data/
│   ├── generate_data.py
│   ├── raw/                     ← generated CSVs (merchants, transactions, settlements, refunds)
│   └── finance_ops.db           ← generated SQLite DB
├── sql/
│   ├── schema.sql                ← production-style Postgres DDL
│   └── validation_checks.sql     ← the 6 reconciliation/DQ checks, as views
├── src/
│   ├── data_validation.py        ← runs the DQ checks, writes reports/data_quality_report.csv
│   ├── reporting.py               ← builds the KPI CSVs
│   └── ai_narrative.py            ← Claude API commentary generator (+ offline demo mode)
├── reports/                      ← all generated output lands here
│   ├── data_quality_report.csv
│   ├── data_quality_details/
│   ├── kpi_daily_summary.csv
│   ├── kpi_merchant_segment.csv
│   ├── kpi_weekly_snapshot.csv
│   └── ai_narrative_offline.md   ← sample output, included so it's reviewable with no setup
└── docs/
    └── dashboard_guide.md         ← how to wire the CSVs into Power BI / Tableau
```

## Running it

```bash
pip install -r requirements.txt
python run_pipeline.py
```

This regenerates the dataset and every report from scratch, in order.
Individual stages can also be run on their own:

```bash
python data/generate_data.py
python src/data_validation.py
python src/reporting.py
python src/ai_narrative.py
```

### Enabling live AI commentary

By default `ai_narrative.py` runs in **offline mode** — a deterministic
template stands in for Claude so the pipeline works with zero setup
(see `reports/ai_narrative_offline.md` for a sample). To generate the
commentary live via the Claude API instead:

```bash
export ANTHROPIC_API_KEY="your-key-here"
python src/ai_narrative.py
```

## The data quality checks, specifically

| Check | What it catches |
|---|---|
| Duplicate transactions | Same merchant/date/amount/method inserted more than once |
| Missing settlements | Successful transactions with no matching settlement record |
| Settlement mismatches | `settled_amount ≠ transaction amount − fee`, beyond rounding tolerance |
| Late settlements | Settled >3 days after the transaction (SLA breach) |
| Orphan refunds | Refund references a `txn_id` that doesn't exist |
| Invalid amounts | Zero or negative transaction amounts |

Each is a real failure mode in payment reconciliation, not a toy example —
this is the same category of issue a business finance analyst at a
payments company would be expected to catch before numbers go into a
report.

## Notes on the data

The dataset is synthetic (seeded, reproducible via `generate_data.py`)
and modeled loosely on typical Indian payments-gateway economics
(UPI/Card/Netbanking/Wallet/EMI mix, ~2.1% take rate). No real
transaction or merchant data is used anywhere in this project.

## Possible extensions

- Swap SQLite for a real Postgres instance (schema.sql is already written for it)
- Schedule `run_pipeline.py` via cron/Airflow for a genuinely "real-time" MIS
- Add a Streamlit front-end for the data-quality drill-through
- Feed the AI narrative back into a Slack/email digest via the Claude API's tool-use
