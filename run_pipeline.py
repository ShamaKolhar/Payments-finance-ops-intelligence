"""Runs all pipeline steps in order. Stops if any step fails."""

import subprocess
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

STEPS = [
    ("Generating data", os.path.join(BASE_DIR, "data", "generate_data.py")),
    ("Running data quality checks", os.path.join(BASE_DIR, "src", "data_validation.py")),
    ("Building KPI reports", os.path.join(BASE_DIR, "src", "reporting.py")),
    ("Writing weekly summary", os.path.join(BASE_DIR, "src", "ai_narrative.py")),
]


def main():
    for i, (label, script) in enumerate(STEPS, start=1):
        print(f"\n[{i}/{len(STEPS)}] {label}")
        result = subprocess.run([sys.executable, script])
        if result.returncode != 0:
            print(f"Step {i} failed, stopping.")
            sys.exit(1)

    print("\nDone. Outputs are in reports/")


if __name__ == "__main__":
    main()
