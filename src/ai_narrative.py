"""
ai_narrative.py
----------------
Takes the KPI weekly
snapshot + data quality summary and asks Claude to draft an
executive-ready written commentary - the kind of first-pass
narrative a finance analyst would otherwise write by hand every
week.

Two modes:
  - LIVE mode: if ANTHROPIC_API_KEY is set in the environment,
    calls the real Claude API (claude-sonnet-4-6).
  - OFFLINE/DEMO mode: if no key is set, uses a deterministic
    template so the pipeline still runs end-to-end and produces
    a representative sample output for review (see
    reports/ai_narrative_sample_offline.md for what this looks like).

Usage:
    python src/ai_narrative.py
"""

import os
import json
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

MODEL = "claude-sonnet-4-6"


def load_inputs():
    weekly = pd.read_csv(os.path.join(REPORTS_DIR, "kpi_weekly_snapshot.csv"))
    dq = pd.read_csv(os.path.join(REPORTS_DIR, "data_quality_report.csv"))
    segment = pd.read_csv(os.path.join(REPORTS_DIR, "kpi_merchant_segment.csv"))
    return weekly, dq, segment


def build_prompt(weekly, dq, segment):
    top_segment = segment.sort_values("gross_amount", ascending=False).iloc[0]
    high_severity_issues = dq[dq["severity"] == "High"]

    prompt = f"""You are a financial analyst assistant writing a weekly business
finance summary for internal stakeholders at a payments company.

Weekly KPI snapshot (this week vs prior week):
{weekly.to_string(index=False)}

Top merchant segment by gross transaction volume: {top_segment['segment']}
  - Gross amount: {top_segment['gross_amount']:.0f}
  - Effective take rate: {top_segment['effective_take_rate_pct']:.2f}%

Data quality issues flagged this run (High severity only):
{high_severity_issues.to_string(index=False)}

Write a concise (150-200 word) executive commentary covering:
1. The headline movement in revenue/volume week-over-week, with likely direction of cause
   (do not invent specific root causes you cannot see in the data - flag them as "worth
   investigating" rather than asserting them as fact).
2. Anything in the refund or failed-transaction rate worth flagging.
3. A one-line callout on the data quality issues, framed as action items for the data team.
Write in plain, direct business English. No bullet points - prose paragraph(s) only.
"""
    return prompt


def call_claude_live(prompt, api_key):
    import urllib.request

    body = json.dumps({
        "model": MODEL,
        "max_tokens": 500,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
    return "\n".join(text_blocks)


def offline_fallback_narrative(weekly, dq, segment):
    """
    Deterministic, template-based narrative used when no API key is
    present, so the pipeline is still fully runnable end-to-end and
    a reviewer can see representative output without needing a key.
    """
    def metric(name):
        row = weekly[weekly["metric"] == name].iloc[0]
        return row["this_week"], row["wow_change_pct"]

    gross, gross_wow = metric("gross_amount")
    fail_rate, fail_wow = metric("avg_failed_txn_rate_pct")
    refund_amt, refund_wow = metric("refund_amount")
    top_segment = segment.sort_values("gross_amount", ascending=False).iloc[0]
    high_sev_count = int(dq[dq["severity"] == "High"]["records_flagged"].sum())

    direction = "declined" if gross_wow < 0 else "grew"
    return (
        f"Gross transaction value {direction} {abs(gross_wow):.1f}% week-over-week to "
        f"INR {gross:,.0f}, led by the {top_segment['segment']} segment "
        f"(effective take rate {top_segment['effective_take_rate_pct']:.2f}%). "
        f"The movement doesn't have a confirmed root cause in this dataset and is worth "
        f"investigating against marketing spend, merchant churn, or seasonality before "
        f"it's flagged upward. The failed-transaction rate sits at {fail_rate:.2f}% "
        f"({'up' if fail_wow > 0 else 'down'} {abs(fail_wow):.1f}% WoW) - within normal "
        f"range but worth a spot-check if it continues trending up. Refund payouts came in "
        f"at INR {refund_amt:,.0f} ({'up' if refund_wow > 0 else 'down'} {abs(refund_wow):.1f}% "
        f"WoW). Separately, this run's data-quality checks flagged {high_sev_count} "
        f"high-severity records (missing settlements, settlement mismatches, duplicate "
        f"transactions, and orphan refunds) - recommend the data team triage these before "
        f"this snapshot is treated as final for reporting.\n\n"
        f"[This is an OFFLINE template-based narrative, generated because no "
        f"ANTHROPIC_API_KEY was set. Set the key to have Claude generate this "
        f"commentary live from the same inputs - see README for setup.]"
    )


def main():
    weekly, dq, segment = load_inputs()
    prompt = build_prompt(weekly, dq, segment)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        print("ANTHROPIC_API_KEY found - calling Claude live...")
        narrative = call_claude_live(prompt, api_key)
        mode = "live"
    else:
        print("No ANTHROPIC_API_KEY set - using offline template fallback.")
        print("(Set the env var to generate this commentary live via the Claude API.)")
        narrative = offline_fallback_narrative(weekly, dq, segment)
        mode = "offline"

    out_path = os.path.join(REPORTS_DIR, f"ai_narrative_{mode}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Weekly Business Finance Commentary\n\n")
        f.write(narrative + "\n")

    print(f"\nNarrative written to: {out_path}")
    print("\n--- PREVIEW ---\n")
    try:
        print(narrative)
    except UnicodeEncodeError:
        # Some Windows terminals default to a codepage that can't print
        # every character; the file on disk (written as utf-8) is always
        # correct regardless of what the console can display.
        print(narrative.encode("ascii", errors="replace").decode("ascii"))


if __name__ == "__main__":
    main()
