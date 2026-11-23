"""Step 4: select the cohort and compute every player's season mean, SD and CV%.

Reads  : data/shared/match_player_features.csv          (one row per player per match)
Writes : data/shared/match_player_features_clean.csv    (matches of eligible players, >= 60 min)
         data/shared/player_season_summary.csv          (one row per player: mean, SD, CV% per metric)
         data/shared/player_season_summary_no_gk.csv    (the same without goalkeepers)

Run from the repository root:
    python scripts/2_analysis/s04_clean_and_summarise.py
"""

from match_variability.cleaning import run

if __name__ == "__main__":
    run()
