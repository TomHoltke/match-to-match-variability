"""
Central configuration: paths and analysis parameters.

All paths are derived from the repository root, so the project runs without
modification on any machine after cloning. Nothing here is machine-specific.
"""

from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths (relative to the repository root)
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"

# Shared input table: one row per player per match.
MATCH_FEATURES_FILE = DATA_DIR / "match_player_features.xlsx"

# Intermediate / derived tables written by the cleaning step.
CLEAN_FILE = DATA_DIR / "match_player_features_clean.xlsx"
PLAYER_SUMMARY_FILE = DATA_DIR / "player_season_summary.xlsx"
PLAYER_SUMMARY_NO_GK_FILE = DATA_DIR / "player_season_summary_no_gk.xlsx"

# --------------------------------------------------------------------------- #
# Inclusion thresholds for the analysis cohort
# --------------------------------------------------------------------------- #
# A player is kept only if they have at least MIN_MATCHES distinct matches in
# which they played at least MIN_MINUTES minutes.
MIN_MATCHES = 17
MIN_MINUTES = 60

# --------------------------------------------------------------------------- #
# Position grouping
# --------------------------------------------------------------------------- #
# Map the fine-grained tracking-provider position labels onto compact groups.
POSITION_GROUP_MAP = {
    "Goalkeeper": "GK",
    "Left Center Back": "CB",
    "Right Center Back": "CB",
    "Center Back": "CB",
    "Left Back": "FB",
    "Right Back": "FB",
    "Left Central Midfield": "CM",
    "Right Central Midfield": "CM",
    "Center Midfield": "CM",
    "Center Defensive Midfield": "CM",
    "Left Defensive Midfield": "CM",
    "Right Defensive Midfield": "CM",
    "Center Attacking Midfield": "AM",
    "Left Attacking Midfield": "AM",
    "Right Attacking Midfield": "AM",
    "Left Midfield": "WM",
    "Right Midfield": "WM",
    "Left Wing": "WF",
    "Right Wing": "WF",
    "Striker": "CF",
    "Left Forward": "CF",
    "Right Forward": "CF",
}
POSITION_GROUP_ORDER = ["GK", "CB", "FB", "CM", "AM", "WM", "WF", "CF", "Other"]

# Positions retained for the linear mixed-model analysis (outfield, well
# represented). CM is the reference category in the models.
ANALYSIS_POSITIONS = ["CM", "CB", "FB", "AM", "CF"]

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
