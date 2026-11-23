"""Step 5: mixed models, Tukey contrasts, and every table and figure of the manuscript.

Reads  : data/shared/player_season_summary.csv, data/shared/match_player_features_clean.csv
Writes : results/manuscript/  Table1.csv, TableS1.csv, TableS2.csv, TableS3.csv,
         Figure1_forest_position_vs_CM.png, Manuscript_tables_and_figure.docx

Run from the repository root:
    python scripts/2_analysis/s05_manuscript_results.py
"""

from match_variability.manuscript_results import run

if __name__ == "__main__":
    run()
