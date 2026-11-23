"""
Cleaning and player-season aggregation.

Pipeline
--------
1. ``clean_player_selection`` — keep only players with at least ``MIN_MATCHES``
   distinct matches of at least ``MIN_MINUTES`` minutes, and return the
   filtered match-level table.
2. ``build_player_summary`` — aggregate the match-level table to one row per
   player: mean, SD and coefficient of variation (CV%) of every per-90 metric
   and every per-event / peak magnitude, plus a primary position group.

Inputs and outputs are CSV files defined in :mod:`match_variability.config`.
The aggregation operates per player and is invariant to row order.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from match_variability.config import (
    CLEAN_FILE,
    MATCH_FEATURES_FILE,
    MIN_MATCHES,
    MIN_MINUTES,
    PLAYER_SUMMARY_FILE,
    PLAYER_SUMMARY_NO_GK_FILE,
    POSITION_GROUP_MAP,
    POSITION_GROUP_ORDER,
)

# Metadata columns carried (unchanged) from the match table into the summary.
_META_COLS = [
    "team_id",
    "team_side",
    "player_id",
    "shirt_num",
    "starter",
    "position_specific",
    "column_id",
]

# Per-event / peak magnitude metrics that are aggregated alongside the
# ``*_per_90`` family (they are already effort-level, never per-90 normalised).
_MAGNITUDE_COLS = [
    "mean_acc_magnitude_ms2",
    "mean_dec_magnitude_ms2",
    "peak_acc_ms2",
    "peak_dec_ms2",
    "mean_sprint_dist_m",
    "mean_sprint_duration_s",
    "mean_peak_speed_ms",
    "max_peak_speed_ms",
    "peak_speed_ms",
]


# --------------------------------------------------------------------------- #
# Step 1 — match-level cleaning
# --------------------------------------------------------------------------- #
def clean_player_selection(
    df: pd.DataFrame,
    min_matches: int = MIN_MATCHES,
    min_minutes: int = MIN_MINUTES,
) -> pd.DataFrame:
    """Filter to players with >= ``min_matches`` matches of >= ``min_minutes``."""
    required = {"MD", "team_id", "player_id", "playing_duration"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    out = df.copy()
    out["MD"] = pd.to_numeric(out["MD"], errors="coerce")
    out["playing_duration"] = pd.to_numeric(out["playing_duration"], errors="coerce")

    out = out.dropna(subset=["MD", "team_id", "player_id", "playing_duration"]).copy()
    out = out[out["playing_duration"] >= min_minutes].copy()

    eligible = (
        out.groupby(["team_id", "player_id"])["MD"]
        .nunique()
        .rename("n_md_meeting_threshold")
        .reset_index()
    )
    eligible = eligible[eligible["n_md_meeting_threshold"] >= min_matches]

    cleaned = (
        out.merge(eligible[["team_id", "player_id"]], on=["team_id", "player_id"], how="inner")
        .sort_values(["team_id", "player_id", "MD"], na_position="last")
        .reset_index(drop=True)
    )

    print(f"[clean_player_selection] min_matches={min_matches}, min_minutes={min_minutes}")
    print(f"  rows={cleaned.shape[0]}  players={cleaned['player_id'].nunique()}  "
          f"teams={cleaned['team_id'].nunique()}")
    return cleaned


# --------------------------------------------------------------------------- #
# Step 2 — player-season aggregation
# --------------------------------------------------------------------------- #
def _mode_or_first(s: pd.Series):
    s = s.dropna()
    if s.empty:
        return np.nan
    m = s.mode()
    return m.iloc[0] if len(m) else s.iloc[0]


def _primary_position_group(base: pd.DataFrame) -> pd.DataFrame:
    """Most frequent position group per player (by distinct matchdays)."""
    grp = base.get("position_specific", pd.Series(index=base.index, dtype=object))
    base = base.assign(
        _position_group=pd.Categorical(
            grp.map(POSITION_GROUP_MAP).fillna("Other"),
            categories=POSITION_GROUP_ORDER, ordered=True,
        )
    )
    counts = (
        base.dropna(subset=["player_id", "MD", "_position_group"])
        .drop_duplicates(subset=["player_id", "MD", "_position_group"])
        .groupby(["player_id", "_position_group"], observed=True)["MD"]
        .nunique()
        .rename("n_md")
        .reset_index()
        .sort_values(["player_id", "n_md"], ascending=[True, False])
    )
    return (
        counts.groupby("player_id", as_index=False)
        .first()[["player_id", "_position_group"]]
        .rename(columns={"_position_group": "position_group_primary"})
    )


def build_player_summary(df_clean: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aggregate the cleaned match table to one row per player.

    Returns ``(summary, summary_no_gk)``. CV columns are expressed in percent.
    """
    meta_cols = [c for c in _META_COLS if c in df_clean.columns]
    per90_cols = [c for c in df_clean.columns if c.endswith("_per_90")]
    extra_cols = [c for c in _MAGNITUDE_COLS if c in df_clean.columns]
    agg_cols = per90_cols + extra_cols

    base = df_clean.copy()
    base["MD"] = pd.to_numeric(base["MD"], errors="coerce")
    base["playing_duration"] = pd.to_numeric(base["playing_duration"], errors="coerce")
    base = base.dropna(subset=["player_id", "MD", "playing_duration"]).copy()

    named_aggs = {c: (c, _mode_or_first) for c in meta_cols if c != "player_id"}
    named_aggs["matches_played"] = ("MD", "nunique")
    named_aggs["playing_duration_mean"] = ("playing_duration", "mean")
    named_aggs["playing_duration_std"] = ("playing_duration", "std")
    for c in agg_cols:
        named_aggs[f"{c}_mean"] = (c, "mean")
        named_aggs[f"{c}_std"] = (c, "std")

    summary = base.groupby("player_id", as_index=False).agg(**named_aggs)

    # Coefficient of variation (fraction for now; converted to % below).
    for c in agg_cols:
        mcol, scol = f"{c}_mean", f"{c}_std"
        if mcol in summary.columns and scol in summary.columns:
            summary[f"{c}_cv"] = summary[scol] / summary[mcol].replace(0, np.nan)
    summary["playing_duration_cv"] = (
        summary["playing_duration_std"] / summary["playing_duration_mean"].replace(0, np.nan)
    )

    # Primary position group + rename of carried specific position.
    summary = summary.merge(_primary_position_group(base), on="player_id", how="left")
    summary["position_group_primary"] = pd.Categorical(
        summary["position_group_primary"].fillna("Other"),
        categories=POSITION_GROUP_ORDER, ordered=True,
    )
    summary = summary.rename(columns={"position_specific": "position_specific_primary"})

    # Column ordering: identifiers, then descriptives, then metric columns.
    front = ["player_id"] + [c for c in meta_cols if c not in ("player_id", "position_specific")]
    front += [
        "position_specific_primary", "position_group_primary", "matches_played",
        "playing_duration_mean", "playing_duration_std", "playing_duration_cv",
    ]
    remaining = [c for c in summary.columns if c not in front]
    sort_keys = ["team_id", "player_id"] if "team_id" in summary.columns else ["player_id"]
    summary = summary[front + remaining].sort_values(sort_keys).reset_index(drop=True)

    # Express all CV columns in percent.
    cv_cols = [c for c in summary.columns if c.endswith("_cv")]
    summary[cv_cols] = summary[cv_cols] * 100

    summary_no_gk = summary[summary["position_specific_primary"] != "Goalkeeper"].copy()

    print(f"[build_player_summary] players={summary['player_id'].nunique()}  "
          f"(no GK: {summary_no_gk['player_id'].nunique()})")
    return summary, summary_no_gk


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run() -> None:
    """Run the full cleaning + aggregation step and write all output files."""
    df = pd.read_csv(MATCH_FEATURES_FILE)
    print(f"Loaded match features: {MATCH_FEATURES_FILE}  shape={df.shape}")

    df_clean = clean_player_selection(df)
    df_clean.to_csv(CLEAN_FILE, index=False)
    print(f"Saved cleaned match table -> {CLEAN_FILE}")

    summary, summary_no_gk = build_player_summary(df_clean)
    summary.to_csv(PLAYER_SUMMARY_FILE, index=False)
    summary_no_gk.to_csv(PLAYER_SUMMARY_NO_GK_FILE, index=False)
    print(f"Saved player summary -> {PLAYER_SUMMARY_FILE}")
    print(f"Saved player summary (no GK) -> {PLAYER_SUMMARY_NO_GK_FILE}")
