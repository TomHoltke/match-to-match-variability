"""
Step 1 — clean the match-feature table and build the player-season summary.

Reads  : data/match_player_features.xlsx          (shared input)
Writes : data/match_player_features_clean.xlsx     (eligible player-matches)
         data/player_season_summary.xlsx           (one row per player)
         data/player_season_summary_no_gk.xlsx      (outfield players only)

Run from the repository root:
    python scripts/01_clean_and_summarise.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.preprocess.cleaning import run

if __name__ == "__main__":
    run()
