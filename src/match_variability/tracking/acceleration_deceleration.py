"""
acceleration_deceleration.py
============================

Per-player Acceleration / Deceleration features for a DataBallPy game.

Output (one row per player that played any minutes):

    -- identifier / metadata --
        player_column_id, full_name, side, shirt_num, position, playing_min

    -- absolute-threshold ±3 m/s² (Cotteret 2025; Harper 2026; Pavo 2025) --
        n_acc_3, n_dec_3                     : event counts
        n_acc_3_per_min, n_dec_3_per_min
        dist_acc_3_m, dist_dec_3_m           : distance while a > +3 / a < −3 m/s²
        dist_acc_3_per_min, dist_dec_3_per_min

    -- high-intensity accel, initial-speed-adjusted (Cotteret 2025) --
        thresholds on peak acceleration vary with the initial running speed:
            standing  (0–1.67 m/s)   → peak a > 4.51 m/s²
            trotting  (1.67–3.00)    → peak a > 3.25 m/s²
            jogging   (3.00–4.17)    → peak a > 2.40 m/s²
            running   (≥ 4.17 m/s)   → peak a > 1.72 m/s²
        n_hi_acc_standing, n_hi_acc_trotting, n_hi_acc_jogging, n_hi_acc_running
        n_acc_SP, n_acc_SP_per_min

    -- per-event magnitude (mean of event peaks) --
        mean_acc_magnitude_ms2 : mean across all ±3 m/s² acc events of the
                                 peak signed acceleration reached in that event
        mean_dec_magnitude_ms2 : mean across all ±3 m/s² dec events of the
                                 peak (most negative) signed acc in that event

    -- match-level peaks --
        peak_acc_ms2           : max signed_acc across the whole match window
        peak_dec_ms2           : min signed_acc (most negative) across the
                                 whole match window (reported as absolute value)

V3 kinematics
--------------
The saved game (V3 pipeline) already contains ``_signed_acceleration``
(d(speed)/dt via central differences on 1 Hz Butterworth-filtered
positions).  This script uses it directly — no re-filtering or
re-deriving needed.

Event-count vs distance
-----------------------
- **Event counts** require a minimum sustained duration (default 3 frames,
  0.12 s @ 25 fps) to filter noise, matching the Tracab recommendation in
  the Cotteret review.
- **Distance in zone** is frame-based and has *no* minimum duration — it
  is a cumulative load metric, so every metre spent above the threshold
  counts, regardless of whether it is part of a discrete "event".

Public entry point
------------------
    compute_acc_dec_features(game) -> pd.DataFrame
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# =============================================================================
# Constants
# =============================================================================
ACC_THRESHOLD = 3.0         # +3 m/s² — most common in literature
DEC_THRESHOLD = -3.0        # −3 m/s²
MIN_EVENT_FRAMES = 3        # 0.12 s @ 25 fps (Cotteret 2025 recommendation)

# Initial running-speed bins (m/s) and their peak-acc thresholds (m/s²).
# Cotteret 2025: players performed maximal sprints from standing and three
# constant initial speeds — trotting ~6.0 km/h (1.67 m/s), jogging ~10.8 km/h
# (3.0 m/s), running ~15.0 km/h (4.17 m/s).  The 75 % amax thresholds are
# 4.51 / 3.25 / 2.40 / 1.72 m/s² respectively.
# Bin boundaries are set at the nominal test speeds, so each bin captures the
# intended initial-speed condition.
INITIAL_SPEED_BINS: list[tuple[str, float, float, float]] = [
    # (label,       lower,   upper,   peak-acc threshold)
    ("standing",    0.00,    1.67,    4.51),   # vinit ≈ 0   → amax 6.01 m/s²
    ("trotting",    1.67,    3.00,    3.25),   # vinit ~1.67 → amax 4.33 m/s²
    ("jogging",     3.00,    4.17,    2.40),   # vinit ~3.00 → amax 3.20 m/s²
    ("running",     4.17,    np.inf,  1.72),   # vinit ~4.17 → amax 2.29 m/s²
]
# Lowest bin threshold — below this any acceleration is trivial regardless of
# initial speed, so we use it as the detection threshold for the scanner.
MIN_HI_THRESHOLD = min(thr for *_r, thr in INITIAL_SPEED_BINS)


# =============================================================================
# Helpers
# =============================================================================
def _extract_events(
    mask: np.ndarray,
    min_len: int = MIN_EVENT_FRAMES,
) -> list[tuple[int, int]]:
    """Return ``(start, end)`` index tuples (end exclusive) for each run of
    consecutive ``True`` values of length ``>= min_len``.
    """
    events: list[tuple[int, int]] = []
    n = len(mask)
    i = 0
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            if (j - i) >= min_len:
                events.append((i, j))
            i = j
        else:
            i += 1
    return events


def _classify_initial_speed(v: float) -> str | None:
    """Return the zone label for an initial running speed (m/s), or None."""
    if np.isnan(v):
        return None
    for label, lo, hi, _thr in INITIAL_SPEED_BINS:
        if lo <= v < hi:
            return label
    return None


def _bin_threshold(label: str) -> float:
    for lbl, _lo, _hi, thr in INITIAL_SPEED_BINS:
        if lbl == label:
            return thr
    raise KeyError(label)


# =============================================================================
# Per-player processing
# =============================================================================
def _process_player(
    side: str,
    player_row: pd.Series,
    tracking: pd.DataFrame,
    fps: float,
    acc_threshold: float,
    dec_threshold: float,
    min_event_frames: int,
) -> dict | None:
    """Compute accel / decel features for one player. Returns ``None`` if the
    player has no usable tracking window."""
    shirt = player_row["shirt_num"]
    if pd.isna(shirt) or int(shirt) == 0:
        return None

    col_id = f"{side}_{int(shirt)}"
    x_col, y_col, v_col = f"{col_id}_x", f"{col_id}_y", f"{col_id}_velocity"
    if any(c not in tracking.columns for c in (x_col, y_col, v_col)):
        return None

    # Restrict to regulation periods and the player's on-pitch frame range.
    mask = tracking["period_id"].isin([1, 2])
    sf, ef = player_row["start_frame"], player_row["end_frame"]
    if sf > 0 and ef > 0:
        mask &= (tracking["frame"] >= sf) & (tracking["frame"] <= ef)
    td = tracking.loc[mask]
    if len(td) < 100:
        return None

    x = td[x_col].to_numpy(dtype=float)
    y = td[y_col].to_numpy(dtype=float)
    speed = td[v_col].to_numpy(dtype=float)

    # Use pre-computed signed acceleration from V3 pipeline.
    sa_col = f"{col_id}_signed_acceleration"
    if sa_col not in tracking.columns:
        return None
    signed_acc = td[sa_col].to_numpy(dtype=float)

    # Playing time from valid speed samples.
    n_valid = int(np.sum(~np.isnan(speed)))
    playing_min = (n_valid / fps) / 60.0
    if playing_min <= 0.0:
        return None

    # Per-frame step distance (NaN where positions are NaN).
    dx = np.diff(x, prepend=x[0])
    dy = np.diff(y, prepend=y[0])
    step = np.sqrt(dx ** 2 + dy ** 2)
    nan_pos = np.isnan(x) | np.isnan(y)
    step[nan_pos] = np.nan

    # -- Frame masks (no min-duration filter — used for cumulative distance) --
    acc_mask = (signed_acc > acc_threshold) & ~np.isnan(signed_acc)
    dec_mask = (signed_acc < dec_threshold) & ~np.isnan(signed_acc)

    dist_acc = float(np.nansum(step[acc_mask]))
    dist_dec = float(np.nansum(step[dec_mask]))

    # -- Event detection (with min duration) --
    acc_events = _extract_events(acc_mask, min_len=min_event_frames)
    dec_events = _extract_events(dec_mask, min_len=min_event_frames)
    n_acc = len(acc_events)
    n_dec = len(dec_events)

    # -- Per-event peak magnitudes (mean across all events) --
    # Peak acc per event = max signed_acc in the event window.
    # Peak dec per event = min signed_acc in the event window (most negative).
    if n_acc > 0:
        acc_peaks = np.array([
            np.nanmax(signed_acc[s:e]) for s, e in acc_events
        ], dtype=float)
        mean_acc_mag = float(np.nanmean(acc_peaks))
    else:
        mean_acc_mag = 0.0

    if n_dec > 0:
        dec_peaks = np.array([
            np.nanmin(signed_acc[s:e]) for s, e in dec_events
        ], dtype=float)
        # Report magnitude as absolute value for readability.
        mean_dec_mag = float(np.nanmean(np.abs(dec_peaks)))
    else:
        mean_dec_mag = 0.0

    # -- Match-level peaks --
    if np.any(~np.isnan(signed_acc)):
        peak_acc = float(np.nanmax(signed_acc))
        peak_dec = float(np.abs(np.nanmin(signed_acc)))
    else:
        peak_acc = 0.0
        peak_dec = 0.0

    # -- Initial-speed-adjusted high-intensity accel counts --
    hi_mask = (signed_acc > MIN_HI_THRESHOLD) & ~np.isnan(signed_acc)
    hi_events = _extract_events(hi_mask, min_len=min_event_frames)
    hi_counts = {lbl: 0 for lbl, *_ in INITIAL_SPEED_BINS}
    for s, e in hi_events:
        # Initial speed = mean speed in the 3 frames immediately before start.
        v0 = float(np.nanmean(speed[max(0, s - 3):max(1, s)]))
        label = _classify_initial_speed(v0)
        if label is None:
            continue
        peak = float(np.nanmax(signed_acc[s:e]))
        if peak > _bin_threshold(label):
            hi_counts[label] += 1
    hi_total = sum(hi_counts.values())

    return {
        "player_column_id":    col_id,
        "full_name":           player_row["full_name"],
        "side":                side,
        "shirt_num":           int(shirt),
        "position":            player_row.get("position_specific", "unknown"),
        "playing_min":         round(playing_min, 2),

        # ── Absolute-threshold counts (±3 m/s²) ─────────────────────────────
        "n_acc_3":             n_acc,
        "n_dec_3":             n_dec,
        "n_acc_3_per_min":     round(n_acc / playing_min, 2),
        "n_dec_3_per_min":     round(n_dec / playing_min, 2),

        # ── Distance in zone (frame-based) ──────────────────────────────────
        "dist_acc_3_m":        round(dist_acc, 1),
        "dist_dec_3_m":        round(dist_dec, 1),
        "dist_acc_3_per_min":  round(dist_acc / playing_min, 2),
        "dist_dec_3_per_min":  round(dist_dec / playing_min, 2),

        # ── Initial-speed-adjusted high-intensity accelerations ─────────────
        "n_hi_acc_standing":   hi_counts["standing"],
        "n_hi_acc_trotting":   hi_counts["trotting"],
        "n_hi_acc_jogging":    hi_counts["jogging"],
        "n_hi_acc_running":    hi_counts["running"],
        "n_acc_SP":            hi_total,
        "n_acc_SP_per_min":    round(hi_total / playing_min, 2),

        # ── Per-event mean magnitudes (mean of event peaks) ─────────────────
        "mean_acc_magnitude_ms2": round(mean_acc_mag, 2),
        "mean_dec_magnitude_ms2": round(mean_dec_mag, 2),

        # ── Match-level peaks (absolute values) ─────────────────────────────
        "peak_acc_ms2":        round(peak_acc, 2),
        "peak_dec_ms2":        round(peak_dec, 2),
    }


# =============================================================================
# Public entry point
# =============================================================================
def compute_acc_dec_features(
    game,
    acc_threshold: float = ACC_THRESHOLD,
    dec_threshold: float = DEC_THRESHOLD,
    min_event_frames: int = MIN_EVENT_FRAMES,
) -> pd.DataFrame:
    """Return per-player accel / decel features for a DataBallPy game.

    Parameters
    ----------
    game             : DataBallPy game object (output of ``get_saved_game``).
    acc_threshold    : signed-acc threshold to count an acceleration (m/s²).
    dec_threshold    : signed-acc threshold to count a deceleration (m/s²).
    min_event_frames : minimum consecutive frames above/below threshold for
                       an *event* (not applied to distance-in-zone).

    Returns
    -------
    pd.DataFrame, one row per player, sorted by descending ``n_acc_3``.
    Empty DataFrame if no players are usable.
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
                acc_threshold=acc_threshold,
                dec_threshold=dec_threshold,
                min_event_frames=min_event_frames,
            )
            if row is not None:
                rows.append(row)

    if not rows:
        return pd.DataFrame()

    return (pd.DataFrame(rows)
              .sort_values("n_acc_3", ascending=False)
              .reset_index(drop=True))
