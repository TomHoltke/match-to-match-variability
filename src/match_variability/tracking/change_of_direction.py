"""
change_of_direction.py
======================

Compute per-player Change of Direction (COD) counts for a DataBallPy game,
classified into Low / Medium / High intensity following the Deutsch et al.
(2025) "red intensity" grid over (COD angle, entry velocity).

V3 kinematics
--------------
The saved game (V3 pipeline) already contains the correct columns:
  - ``{player}_x``, ``{player}_y``  — 1 Hz Butterworth-filtered positions
  - ``{player}_velocity``           — scalar speed (central diff, no filter)
  - ``{player}_signed_acceleration``— d(speed)/dt (central diff, no filter)

This script uses those directly — no re-filtering or re-deriving.

Intensity definition (Deutsch et al. 2025):
    Low     : angle in [20°, 60°)   AND entry velocity <  3.0 m/s
    Medium  : (angle in [60°, 120°)  AND entry velocity <  5.5 m/s)
              OR (angle in [20°, 60°) AND 3.0 <= entry velocity < 5.5 m/s)
    High    : every other valid COD event (angle >= 20°) that is
              harder than the above — i.e. higher angle and/or higher
              entry velocity.

Public entry point
------------------
    compute_cod_features(game) -> pd.DataFrame

Returns one row per player that played any minutes, with columns:
    player_column_id, full_name, side, shirt_num, position, playing_min,
    CoD_low, CoD_medium, CoD_high, CoD_total
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# =============================================================================
# COD state machine (Deutsch et al. 2025)
# =============================================================================
def detect_cod_events(
    signed_acc: np.ndarray,
    xy: np.ndarray,
    speed: np.ndarray,
    decel_threshold: float = -2.0,
    accel_threshold: float = +2.0,
    max_total_length: int = 125,
    min_cod_angle: float = 20.0,
) -> pd.DataFrame:
    """Detect COD events by the Deutsch et al. (2025) state machine.

    An event is a decel phase (signed_acc < −2 m/s²) immediately followed,
    within 25 frames, by an accel phase (signed_acc > +2 m/s²). The COD
    angle is the angle between the decel displacement vector V1 and the
    accel displacement vector V2; only events with angle >= ``min_cod_angle``
    are kept.

    Parameters
    ----------
    signed_acc       : 1-D signed acceleration [m/s²].
    xy               : (N, 2) array of smoothed positions [m].
    speed            : 1-D scalar speed [m/s] (used for entry velocity).
    decel_threshold  : start/end threshold for the decel phase.
    accel_threshold  : start/end threshold for the accel phase.
    max_total_length : max number of frames from decel start to accel end.
    min_cod_angle    : minimum COD angle in degrees (paper default: 20°).

    Returns
    -------
    DataFrame with one row per detected event and columns
    ``Decel Start``, ``Decel End``, ``Accel Start``, ``Accel End``,
    ``COD Angle [deg]``, ``Entry Velocity [m/s]``.
    """
    data = signed_acc
    n = len(data)

    decel_starts: list[int] = []
    decel_ends:   list[int] = []
    accel_starts: list[int] = []
    accel_ends:   list[int] = []
    cod_angles:   list[float] = []
    entry_vels:   list[float] = []

    in_decel = False
    decel_start_idx: int | None = None

    i = 0
    while i < n:
        value = data[i]

        # --- Enter decel phase --------------------------------------------
        if (not in_decel and not np.isnan(value)
                and -8.0 < value < decel_threshold):
            in_decel = True
            decel_start_idx = i

        # --- Leave decel phase → look for a matching accel phase ----------
        elif in_decel and (np.isnan(value) or value >= decel_threshold):
            in_decel = False
            decel_end_idx = i

            # Reject walking drifts (decel longer than 3 s at 25 fps).
            if (decel_end_idx - decel_start_idx) >= 75:
                decel_start_idx = None
                i += 1
                continue

            # Find accel start within 25 frames of decel end.
            accel_start_idx: int | None = None
            for j in range(decel_end_idx + 1,
                           min(decel_end_idx + 26, n)):
                vj = data[j]
                if not np.isnan(vj) and accel_threshold <= vj < 8.0:
                    accel_start_idx = j
                    break
            if accel_start_idx is None:
                decel_start_idx = None
                i += 1
                continue

            # Find accel end — first frame where signed_acc drops below thr.
            accel_end_idx: int | None = None
            for k in range(accel_start_idx + 1,
                           min(accel_start_idx + max_total_length + 1, n)):
                vk = data[k]
                if np.isnan(vk) or vk < accel_threshold:
                    accel_end_idx = k
                    break
            if accel_end_idx is None:
                decel_start_idx = None
                i += 1
                continue

            # Reject events that are too long or contain NaN in the window.
            total_len = accel_end_idx - decel_start_idx + 1
            nan_window_start = max(0, decel_start_idx - 25)
            nan_window_end   = min(n, accel_end_idx + 25)
            has_nan = np.isnan(data[nan_window_start:nan_window_end]).any()
            if total_len > max_total_length or has_nan:
                decel_start_idx = None
                i += 1
                continue

            # --- COD angle via decel / accel displacement vectors ---------
            dec_slice = xy[max(0, decel_start_idx - 1):decel_end_idx]
            acc_slice = xy[accel_start_idx:accel_end_idx + 1]
            if len(dec_slice) < 2 or len(acc_slice) < 2:
                i += 1
                continue

            V1 = dec_slice[-1] - dec_slice[0]
            V2 = acc_slice[-1] - acc_slice[0]
            norm_V1 = float(np.linalg.norm(V1))
            norm_V2 = float(np.linalg.norm(V2))
            if norm_V1 == 0.0 or norm_V2 == 0.0:
                i += 1
                continue

            cos_theta = np.clip(np.dot(V1, V2) / (norm_V1 * norm_V2), -1.0, 1.0)
            cod_angle = float(np.degrees(np.arccos(cos_theta)))
            if cod_angle < min_cod_angle:
                i += 1
                continue

            # Entry velocity = mean scalar speed in the 5 frames before decel.
            s = decel_start_idx
            entry_vel = float(np.nanmean(
                speed[max(0, s - 6):max(0, s - 1)]
            ))

            decel_starts.append(decel_start_idx)
            decel_ends.append(decel_end_idx)
            accel_starts.append(accel_start_idx)
            accel_ends.append(accel_end_idx)
            cod_angles.append(cod_angle)
            entry_vels.append(entry_vel)

        i += 1

    return pd.DataFrame({
        "Decel Start":           decel_starts,
        "Decel End":             decel_ends,
        "Accel Start":           accel_starts,
        "Accel End":             accel_ends,
        "COD Angle [deg]":       cod_angles,
        "Entry Velocity [m/s]":  entry_vels,
    })


# =============================================================================
# Intensity classification (Deutsch et al. grid)
# =============================================================================
def classify_cod_intensity(angle: float, entry_vel: float) -> str | None:
    """Classify one COD event into ``low`` / ``medium`` / ``high``.

    Returns ``None`` if angle or entry velocity is NaN.
    """
    if np.isnan(angle) or np.isnan(entry_vel):
        return None

    # Low — shallow turn at slow entry speed.
    if 20.0 <= angle < 60.0 and entry_vel < 3.0:
        return "low"

    # Medium — moderate angle OR moderate speed.
    medium_band_1 = (60.0 <= angle < 120.0) and (entry_vel < 5.5)
    medium_band_2 = (20.0 <= angle < 60.0) and (3.0 <= entry_vel < 5.5)
    if medium_band_1 or medium_band_2:
        return "medium"

    # Everything else harder than the above.
    return "high"


def _playing_minutes(speed: np.ndarray, fps: float, cap_min: float = 105.0) -> float:
    """Approximate playing minutes from non-NaN speed samples (capped)."""
    n_frames = int(np.sum(~np.isnan(speed)))
    minutes = (n_frames / fps) / 60.0
    return float(min(minutes, cap_min))


# =============================================================================
# Per-player processing
# =============================================================================
def _process_player(
    side: str,
    player_row: pd.Series,
    tracking: pd.DataFrame,
    fps: float,
    decel_threshold: float,
    accel_threshold: float,
    max_total_length: int,
    min_cod_angle: float,
) -> dict | None:
    """Run the full COD pipeline for one player and return counts + metadata.

    Returns ``None`` when the player cannot be processed (missing columns,
    no playing time, etc.).
    """
    shirt = player_row["shirt_num"]
    if pd.isna(shirt) or int(shirt) == 0:
        return None

    col_id = f"{side}_{int(shirt)}"
    x_col, y_col = f"{col_id}_x", f"{col_id}_y"
    v_col = f"{col_id}_velocity"
    required_cols = (x_col, y_col, v_col)
    if any(c not in tracking.columns for c in required_cols):
        return None

    # Periods 1 & 2 only, and only within the player's on-pitch frame range.
    mask = tracking["period_id"].isin([1, 2])
    sf, ef = player_row["start_frame"], player_row["end_frame"]
    if sf > 0 and ef > 0:
        mask &= (tracking["frame"] >= sf) & (tracking["frame"] <= ef)

    td = tracking.loc[mask]
    if len(td) < 100:           # < 4 s on pitch — skip
        return None

    x = td[x_col].to_numpy(dtype=float)
    y = td[y_col].to_numpy(dtype=float)

    speed = td[v_col].to_numpy(dtype=float)

    # Use pre-computed signed acceleration from V3 pipeline.
    sa_col = f"{col_id}_signed_acceleration"
    if sa_col not in tracking.columns:
        return None
    signed_acc = td[sa_col].to_numpy(dtype=float)

    playing_min = _playing_minutes(speed, fps)
    if playing_min <= 0.0:
        return None

    # COD detection.
    xy = np.column_stack([x, y])
    events = detect_cod_events(
        signed_acc=signed_acc,
        xy=xy,
        speed=speed,
        decel_threshold=decel_threshold,
        accel_threshold=accel_threshold,
        max_total_length=max_total_length,
        min_cod_angle=min_cod_angle,
    )

    # Classify each event and tally per-intensity counts.
    counts = {"low": 0, "medium": 0, "high": 0}
    for _, ev in events.iterrows():
        label = classify_cod_intensity(
            ev["COD Angle [deg]"], ev["Entry Velocity [m/s]"]
        )
        if label is not None:
            counts[label] += 1

    return {
        "player_column_id": col_id,
        "full_name":        player_row["full_name"],
        "side":             side,
        "shirt_num":        int(shirt),
        "position":         player_row.get("position_specific", "unknown"),
        "playing_min":      round(playing_min, 2),
        "CoD_low":          counts["low"],
        "CoD_medium":       counts["medium"],
        "CoD_high":         counts["high"],
        "CoD_total":        counts["low"] + counts["medium"] + counts["high"],
    }


# =============================================================================
# Public entry point
# =============================================================================
def compute_cod_features(
    game,
    decel_threshold: float = -2.0,
    accel_threshold: float = +2.0,
    max_total_length: int = 125,
    min_cod_angle: float = 20.0,
) -> pd.DataFrame:
    """Return per-player COD counts (Low / Medium / High) for a game.

    Parameters
    ----------
    game             : DataBallPy game object (output of ``get_saved_game``).
    decel_threshold  : signed-acceleration threshold to enter the decel phase.
    accel_threshold  : signed-acceleration threshold to enter the accel phase.
    max_total_length : max frames from decel start to accel end.
    min_cod_angle    : minimum COD angle in degrees (paper default 20°).

    Returns
    -------
    pd.DataFrame with one row per player that had any playing minutes, and
    columns: ``player_column_id``, ``full_name``, ``side``, ``shirt_num``,
    ``position``, ``playing_min``, ``CoD_low``, ``CoD_medium``,
    ``CoD_high``, ``CoD_total``.
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
                decel_threshold=decel_threshold,
                accel_threshold=accel_threshold,
                max_total_length=max_total_length,
                min_cod_angle=min_cod_angle,
            )
            if row is not None:
                rows.append(row)

    if not rows:
        return pd.DataFrame(columns=[
            "player_column_id", "full_name", "side", "shirt_num", "position",
            "playing_min", "CoD_low", "CoD_medium", "CoD_high", "CoD_total",
        ])

    return (pd.DataFrame(rows)
              .sort_values("CoD_total", ascending=False)
              .reset_index(drop=True))
