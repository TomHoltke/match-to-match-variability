"""Paths and analysis parameters. All other code gets its paths from here.

Shared data and results live inside the repository, so the analysis
(scripts/2_analysis) runs after cloning without any configuration.

The tracking pipeline (scripts/1_tracking_pipeline) also needs the private,
non-shared data: raw tracking files, saved games, the identified feature table
and the pseudonymisation keys. Their location is read from config/paths.toml
(gitignored, one per machine, copied from config/paths.example.toml). If that
file is missing, the defaults below (inside data/private/) are used.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# --------------------------------------------------------------------------- #
# Shared data (in git) and results (in git)
# --------------------------------------------------------------------------- #
SHARED_DIR = REPO_ROOT / "data" / "shared"

# Input of the analysis: one row per player per match (pseudonymised).
MATCH_FEATURES_FILE = SHARED_DIR / "match_player_features.csv"

# Made by scripts/2_analysis/s04_clean_and_summarise.py
CLEAN_FILE = SHARED_DIR / "match_player_features_clean.csv"
PLAYER_SUMMARY_FILE = SHARED_DIR / "player_season_summary.csv"
PLAYER_SUMMARY_NO_GK_FILE = SHARED_DIR / "player_season_summary_no_gk.csv"

# Made by scripts/2_analysis/s05_manuscript_results.py
RESULTS_DIR = REPO_ROOT / "results" / "manuscript"

# --------------------------------------------------------------------------- #
# Private data (never in git): only needed for scripts/1_tracking_pipeline
# --------------------------------------------------------------------------- #
PATHS_FILE = REPO_ROOT / "config" / "paths.toml"
_PRIVATE_DEFAULTS = {
    "PRIVATE_DIR": "data/private",
    "RAW_TRACKING_DIR": "data/private/raw_tracking",
    "SAVED_GAMES_DIR": "data/private/saved_games_v3",
}


def _private_paths() -> dict[str, Path]:
    """Private paths from config/paths.toml, falling back to the defaults.

    A relative path is read from the repository folder.
    """
    paths = dict(_PRIVATE_DEFAULTS)
    if PATHS_FILE.exists():
        with PATHS_FILE.open("rb") as f:
            paths.update(tomllib.load(f))
    return {k: (REPO_ROOT / v).resolve() for k, v in paths.items()}


_P = _private_paths()
PRIVATE_DIR = _P["PRIVATE_DIR"]
RAW_TRACKING_DIR = _P["RAW_TRACKING_DIR"]      # TRACAB .dat + metadata.xml, Opta f24.xml + f7.xml
SAVED_GAMES_DIR = _P["SAVED_GAMES_DIR"]        # one DataBallPy saved game per match (step 1)

# Which raw matches go in, their saved-game name and matchday (see docs/tracking_pipeline.md).
MATCH_LIST_FILE = PRIVATE_DIR / "match_list.csv"
# Feature table with real names and provider ids (step 2).
IDENTIFIED_FEATURES_FILE = PRIVATE_DIR / "features_identified" / "match_player_features_identified.parquet"
# Pseudonymisation keys: real id <-> neutral code (step 3).
PLAYER_KEY_FILE = PRIVATE_DIR / "keys" / "player_id_crosswalk.csv"
TEAM_KEY_FILE = PRIVATE_DIR / "keys" / "team_id_crosswalk.csv"

# --------------------------------------------------------------------------- #
# Inclusion thresholds for the analysis cohort
# --------------------------------------------------------------------------- #
# A player is kept only if they have at least MIN_MATCHES distinct matches in
# which they played at least MIN_MINUTES minutes (17 = half of 34 matchdays).
MIN_MATCHES = 17
MIN_MINUTES = 60

# --------------------------------------------------------------------------- #
# Position grouping
# --------------------------------------------------------------------------- #
# Map the detailed position labels (from the starting formation, see
# tracking/positions.py) onto compact groups.
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
