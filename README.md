# Payments Finance Ops Intelligence

Data quality checks and weekly KPI reporting for a (synthetic) payments company, with an optional LLM-written weekly summary.

The idea: a finance team at a payment gateway gets transaction, settlement and refund data every day. Before any of it goes into a report, someone has to check that it actually reconciles. This project does those checks in SQL, builds the KPI tables from the clean data, and drafts the weekly commentary so the analyst only has to edit it.

## Pipeline

```
generate_data.py -> finance_ops.db -> data_validation.py -> data_quality_report.csv
                                   -> reporting.py       -> kpi_*.csv -> Tableau
                                                         -> ai_narrative.py -> ai_narrative_*.md
```

1. **Data** - `data/generate_data.py` creates 60 merchants and ~12k transactions (Jun-Aug 2026) plus settlements and refunds. I added some common reconciliation problems on purpose so the checks have something to find.
2. **Validation** - `sql/validation_checks.sql` defines 6 checks as views. `src/data_validation.py` runs them and writes a summary plus the flagged rows for each check.
3. **Reporting** - `src/reporting.py` builds daily KPIs, segment-level revenue/take rate and a week-over-week snapshot.
4. **Commentary** - `src/ai_narrative.py` sends the weekly snapshot and the high-severity DQ issues to the Claude API and asks for a short summary. Without an API key it falls back to a fixed template.
5. **Dashboard** - `reports/Payments Finance - Weekly Statement.twb` is a Tableau workbook built on the KPI and data quality CSVs.

## Data quality checks

| Check | Rule | Severity |
|---|---|---|
| Duplicate transactions | same merchant, date, amount and method more than once | High |
| Missing settlements | successful txn with no settlement row | High |
| Settlement mismatch | `settled_amount` differs from `amount - fee` by more than Rs 1 | High |
| Orphan refunds | refund `txn_id` not found in transactions | High |
| Late settlements | settled more than 3 days after txn date | Medium |
| Invalid amounts | amount <= 0 | Medium |

On the last run these flagged 464 high-severity records (mostly missing settlements and settlement mismatches), about 3.8% of transactions.

## How to run

```bash
pip install -r requirements.txt
python run_pipeline.py
```

Or run each step on its own:

```bash
python data/generate_data.py
python src/data_validation.py
python src/reporting.py
python src/ai_narrative.py
```

For the live LLM summary, set your key first:

```bash
export ANTHROPIC_API_KEY="..."
python src/ai_narrative.py
```

`reports/ai_narrative_offline.md` shows the output of the offline fallback.

## Project structure

```
data/      generate_data.py, raw CSVs, SQLite db
sql/       schema.sql (Postgres version of the tables), validation_checks.sql
src/       data_validation.py, reporting.py, ai_narrative.py
reports/   generated CSVs, DQ detail files, Tableau workbook
```

## Notes

- All data is synthetic and seeded (seed 42), so reruns give the same numbers. Amounts are in INR and the fee is a flat 2.1%, roughly in line with Indian gateway pricing.
- The pipeline runs on SQLite so it needs no setup. `schema.sql` is the Postgres version of the same tables.
- `refunds.txn_id` has no foreign key on purpose, otherwise orphan refunds couldn't be loaded and checked.
- The late settlement check counts calendar days, so anything settled over a weekend also gets flagged. That's why it catches ~11% of settlements when only ~3% were made late in the data. Changing it to business days is on the list below.

## Things I'd add next

- Count business days (not calendar days) in the late settlement check
- Move to Postgres and schedule the pipeline (Airflow)
- Exclude flagged records from the KPIs instead of only reporting them
- Send the weekly summary to Slack or email
