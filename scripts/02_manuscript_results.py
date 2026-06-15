"""
Step 2 — final manuscript tables and figure.

Reads  : data/player_season_summary.xlsx
Writes : results/manuscript/  (Table1, TableS1–S3, Figure 1, Word document)

Run from the repository root:
    python scripts/02_manuscript_results.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analysis.manuscript_results import run

if __name__ == "__main__":
    run()
