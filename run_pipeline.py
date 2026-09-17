"""
run_pipeline.py
----------------
One-command entry point that runs the full pipeline in order:
  1. Generate synthetic data (data/generate_data.py)
  2. Run data-quality validation (src/data_validation.py)
  3. Build business KPI reports (src/reporting.py)
  4. Generate AI executive commentary (src/ai_narrative.py)

Usage:
    python run_pipeline.py
"""

import subprocess
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

STEPS = [
    ("Generating synthetic finance data", os.path.join(BASE_DIR, "data", "generate_data.py")),
    ("Running data quality validation", os.path.join(BASE_DIR, "src", "data_validation.py")),
    ("Building business KPI reports", os.path.join(BASE_DIR, "src", "reporting.py")),
    ("Generating AI executive commentary", os.path.join(BASE_DIR, "src", "ai_narrative.py")),
]


def main():
    for i, (label, script) in enumerate(STEPS, start=1):
        print(f"\n{'=' * 70}\nSTEP {i}/{len(STEPS)}: {label}\n{'=' * 70}")
        result = subprocess.run([sys.executable, script])
        if result.returncode != 0:
            print(f"\nPipeline stopped: step {i} ({label}) failed.")
            sys.exit(1)

    print(f"\n{'=' * 70}\nPipeline complete. See the reports/ folder for all outputs.\n{'=' * 70}")


if __name__ == "__main__":
    main()
