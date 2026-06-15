"""
sprint.py  (reference only — requires raw tracking data)
========================================================

Per-player sprint features for a DataBallPy game.

Sprint definition (IndPlayerProfileMetrics.pdf; Jiménez Rubio et al., 2024;
Gualtieri et al., 2023; Cotteret et al., 2025):

    A sprint is a continuous period of running **above 25.2 km/h (7.0 m/s)**.
    - Entry: speed rises above 7.0 m/s.
    - Exit: speed falls below the hysteresis threshold of 24.0 km/h (6.67 m/s).
      The hysteresis band avoids splitting one effort into multiple events when
      speed briefly dips below the threshold.
    - Minimum distance: 1 m while above threshold (Linke et al., 2018/2020).

V3 kinematics: ``{player}_velocity`` is derived from 1 Hz Butterworth-
filtered positions via central differences (no additional velocity filter).
Speeds in the sprint zone do not require further filtering
(Linke et al., 2020: Tracab peak speed differs < 0.5% from VICON).

Output (one row per player with usable tracking data)
------------------------------------------------------
    -- identifier / metadata --
        player_column_id, full_name, side, shirt_num, position, playing_min

    -- sprint counts & distance --
        n_sprints              : number of discrete sprint efforts
        n_sprints_per_min
        sprint_distance_m      : total distance covered while above threshold (m)
        sprint_distance_per_min

    -- per-effort characteristics (mean across all sprint efforts) --
        mean_sprint_dist_m     : mean distance per effort (m)
        mean_sprint_duration_s : mean duration per effort (s)
        mean_peak_speed_ms     : mean peak speed reached per effort (m/s)
        max_peak_speed_ms      : highest peak speed across all efforts (m/s)

    -- match-level peak speed --
        peak_speed_ms          : maximum scalar speed across the whole match
                                 window (periods 1 & 2, player on-pitch range),
                                 independent of sprint detection.

Public entry point
------------------
    compute_sprint_features(game) -> pd.DataFrame
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# =============================================================================
# Constants
# =============================================================================
SPRINT_THRESHOLD_MS  = 7.0          # 25.2 km/h  — entry threshold
SPRINT_HYSTERESIS_MS = 6.667        # 24.0 km/h  — exit (hysteresis) threshold
MIN_SPRINT_DIST_M    = 1.0          # minimum distance above threshold to count


# =============================================================================
# Helpers
# =============================================================================
def _detect_sprint_efforts(
    speed: np.ndarray,
    step: np.ndarray,
    fps: float,
    threshold: float = SPRINT_THRESHOLD_MS,
    hysteresis: float = SPRINT_HYSTERESIS_MS,
    min_dist_m: float = MIN_SPRINT_DIST_M,
) -> list[dict]:
    """Detect discrete sprint efforts with hysteresis gating.

    Parameters
    ----------
    speed      : 1-D scalar speed (m/s), NaN where player is off-pitch.
    step       : per-frame distance (m); NaN where positions are NaN.
    fps        : sampling rate in Hz.
    threshold  : entry speed (m/s).
    hysteresis : exit speed (m/s) — must be <= threshold.
    min_dist_m : minimum distance covered above threshold for a valid effort.

    Returns
    -------
    List of dicts, one per valid sprint effort, with keys:
        start_frame, end_frame, duration_s, distance_m, peak_speed_ms,
        entry_speed_ms, exit_speed_ms.
    """
    n = len(speed)
    efforts: list[dict] = []
    in_sprint = False
    start = 0

    i = 0
    while i < n:
        v = speed[i]
        if np.isnan(v):
            if in_sprint:
                # NaN gap — end the current sprint.
                in_sprint = False
            i += 1
            continue

        if not in_sprint and v >= threshold:
            in_sprint = True
            start = i

        elif in_sprint and v < hysteresis:
            # Sprint ended — evaluate.
            end = i  # exclusive
            dist = float(np.nansum(step[start:end]))
            if dist >= min_dist_m:
                seg_speed = speed[start:end]
                efforts.append({
                    "start_frame":    start,
                    "end_frame":      end,
                    "duration_s":     (end - start) / fps,
                    "distance_m":     dist,
                    "peak_speed_ms":  float(np.nanmax(seg_speed)),
                    "entry_speed_ms": float(speed[start]),
                    "exit_speed_ms":  float(speed[end - 1]),
                })
            in_sprint = False

        i += 1

    # Close an open sprint at the end of the array.
    if in_sprint:
        end = n
        dist = float(np.nansum(step[start:end]))
        if dist >= min_dist_m:
            seg_speed = speed[start:end]
            efforts.append({
                "start_frame":    start,
                "end_frame":      end,
                "duration_s":     (end - start) / fps,
                "distance_m":     dist,
                "peak_speed_ms":  float(np.nanmax(seg_speed)),
                "entry_speed_ms": float(speed[start]),
                "exit_speed_ms":  float(speed[end - 1]),
            })

    return efforts


# =============================================================================
# Per-player processing
# =============================================================================
def _process_player(
    side: str,
    player_row: pd.Series,
    tracking: pd.DataFrame,
    fps: float,
    threshold: float,
    hysteresis: float,
    min_dist_m: float,
) -> dict | None:
    """Compute sprint features for one player. Returns None if not usable."""
    shirt = player_row["shirt_num"]
    if pd.isna(shirt) or int(shirt) == 0:
        return None

    col_id = f"{side}_{int(shirt)}"
    x_col, y_col, v_col = f"{col_id}_x", f"{col_id}_y", f"{col_id}_velocity"
    if any(c not in tracking.columns for c in (x_col, y_col, v_col)):
        return None

    # Regulation periods and player's on-pitch frame range.
    mask = tracking["period_id"].isin([1, 2])
    sf, ef = player_row["start_frame"], player_row["end_frame"]
    if sf > 0 and ef > 0:
        mask &= (tracking["frame"] >= sf) & (tracking["frame"] <= ef)
    td = tracking.loc[mask]
    if len(td) < 100:
        return None

    speed = td[v_col].to_numpy(dtype=float)
    speed = np.where(speed > 12.0, np.nan, speed)   # hard cap — 43 km/h

    x = td[x_col].to_numpy(dtype=float)
    y = td[y_col].to_numpy(dtype=float)
    dx = np.diff(x, prepend=x[0])
    dy = np.diff(y, prepend=y[0])
    step = np.sqrt(dx ** 2 + dy ** 2)
    step[np.isnan(x) | np.isnan(y)] = np.nan

    # Playing time from valid speed samples.
    n_valid = int(np.sum(~np.isnan(speed)))
    playing_min = (n_valid / fps) / 60.0
    if playing_min <= 0.0:
        return None

    # Sprint detection.
    efforts = _detect_sprint_efforts(
        speed=speed,
        step=step,
        fps=fps,
        threshold=threshold,
        hysteresis=hysteresis,
        min_dist_m=min_dist_m,
    )

    n_sprints = len(efforts)
    sprint_dist = sum(e["distance_m"] for e in efforts)

    if n_sprints > 0:
        mean_dist   = float(np.mean([e["distance_m"]    for e in efforts]))
        mean_dur    = float(np.mean([e["duration_s"]     for e in efforts]))
        mean_peak   = float(np.mean([e["peak_speed_ms"]  for e in efforts]))
        max_peak    = float(np.max ([e["peak_speed_ms"]  for e in efforts]))
    else:
        mean_dist = mean_dur = mean_peak = max_peak = 0.0

    # Match-level peak speed (max across whole window, cap already applied).
    peak_speed = float(np.nanmax(speed)) if np.any(~np.isnan(speed)) else 0.0

    return {
        "player_column_id":       col_id,
        "full_name":              player_row["full_name"],
        "side":                   side,
        "shirt_num":              int(shirt),
        "position":               player_row.get("position_specific", "unknown"),
        "playing_min":            round(playing_min, 2),

        # ── Count & distance ────────────────────────────────────────────────
        "n_sprints":              n_sprints,
        "n_sprints_per_min":      round(n_sprints / playing_min, 3),
        "sprint_distance_m":      round(sprint_dist, 1),
        "sprint_distance_per_min": round(sprint_dist / playing_min, 2),

        # ── Per-effort means ────────────────────────────────────────────────
        "mean_sprint_dist_m":     round(mean_dist, 1),
        "mean_sprint_duration_s": round(mean_dur, 2),
        "mean_peak_speed_ms":     round(mean_peak, 2),
        "max_peak_speed_ms":      round(max_peak, 2),

        # ── Match-level peak speed (independent of sprint detection) ────────
        "peak_speed_ms":          round(peak_speed, 2),
    }


# =============================================================================
# Public entry point
# =============================================================================
def compute_sprint_features(
    game,
    threshold_ms:  float = SPRINT_THRESHOLD_MS,
    hysteresis_ms: float = SPRINT_HYSTERESIS_MS,
    min_dist_m:    float = MIN_SPRINT_DIST_M,
) -> pd.DataFrame:
    """Return per-player sprint features for a DataBallPy game.

    Parameters
    ----------
    game           : DataBallPy game object (output of ``get_saved_game``).
    threshold_ms   : entry speed threshold in m/s (default 7.0 = 25.2 km/h).
    hysteresis_ms  : exit speed threshold in m/s (default 6.667 = 24.0 km/h).
    min_dist_m     : minimum distance above threshold for a valid sprint (m).

    Returns
    -------
    pd.DataFrame, one row per player, sorted by descending ``n_sprints``.
    """
    tracking = (game.tracking_data.data
                if hasattr(game.tracking_data, "data")
                else game.tracking_data)
    fps = game.tracking_data.frame_rate

    rows: list[dict] = []
    for side in ("home", "away"):
        players_df = getattr(game, f"{side}_players")
        for _, p_row in players_df.iterrows():
            row = _process_player(
                side=side,
                player_row=p_row,
                tracking=tracking,
                fps=fps,
                threshold=threshold_ms,
                hysteresis=hysteresis_ms,
                min_dist_m=min_dist_m,
            )
            if row is not None:
                rows.append(row)

    if not rows:
        return pd.DataFrame()

    return (pd.DataFrame(rows)
              .sort_values("n_sprints", ascending=False)
              .reset_index(drop=True))
