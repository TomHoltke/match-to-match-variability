"""Player kinematics from raw positions: filtered positions, speed and signed acceleration.

Per player (TRACAB, 25 Hz):
  1. 4th-order zero-lag Butterworth low-pass filter (1 Hz cut-off) on x and y
     (Deutsch et al., 2025; Linke et al., 2020).
  2. Velocity by central differences (np.gradient) of the filtered positions,
     no further filter. Speeds above 12 m/s are set to missing.
  3. Signed acceleration = d(speed)/dt by central differences, no further
     filter (positive = speeding up, negative = slowing down). Values beyond
     +-10 m/s2 are set to missing.

The result is stored in the saved game as ``{player}_x``, ``{player}_y``,
``{player}_velocity``, ``{player}_signed_acceleration`` (and the absolute
value as ``{player}_acceleration``). All feature modules read these columns.

Unchanged from the code that produced the shared data ("V3" pipeline).
"""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, filtfilt

from match_variability.tracking.positions import add_position_specific

# Butterworth filter settings
BW_CUTOFF_HZ = 1.0
BW_ORDER = 4

# Speed / acceleration caps
MAX_PLAYER_SPEED_MS = 12.0      # 43.2 km/h, hard cap
MAX_SIGNED_ACC_MS2 = 10.0       # +-10 m/s2, set to missing beyond this


def _butterworth_lowpass_1d(signal: np.ndarray, fps: float, cutoff_hz: float,
                            order: int) -> np.ndarray:
    """Zero-phase Butterworth low-pass filter.  NaN-safe."""
    nan_mask = np.isnan(signal)
    if (~nan_mask).sum() < order * 3:
        return signal.copy()
    idx = np.arange(len(signal))
    sig = np.interp(idx, idx[~nan_mask], signal[~nan_mask])
    b, a = butter(order, cutoff_hz / (fps / 2.0), btype="low")
    filtered = filtfilt(b, a, sig)
    filtered[nan_mask] = np.nan
    return filtered


def apply_player_kinematics(game) -> None:
    """Apply the player kinematics pipeline IN PLACE on the game's tracking data.

    Steps per player column_id:
      1. Butterworth low-pass (1 Hz, 4th order) on _x and _y
      2. Velocity via central difference (np.gradient) on filtered positions
         → _vx, _vy, _velocity   (no additional filter)
      3. Signed acceleration = d(speed)/dt via central difference on _velocity
         → _signed_acceleration   (positive = speeding up)
    """
    tracking = (game.tracking_data.data
                if hasattr(game.tracking_data, "data")
                else game.tracking_data)
    fps = game.tracking_data.frame_rate
    dt = 1.0 / fps
    column_ids = game.get_column_ids()

    print(f"    kinematics: {len(column_ids)} player columns @ {fps} Hz")

    for col_id in column_ids:
        x_col = f"{col_id}_x"
        y_col = f"{col_id}_y"
        if x_col not in tracking.columns or y_col not in tracking.columns:
            continue

        # ── 1. Butterworth filter on raw positions ──────────────────────
        x_raw = tracking[x_col].values.astype(float)
        y_raw = tracking[y_col].values.astype(float)

        x_filt = _butterworth_lowpass_1d(x_raw, fps, BW_CUTOFF_HZ, BW_ORDER)
        y_filt = _butterworth_lowpass_1d(y_raw, fps, BW_CUTOFF_HZ, BW_ORDER)

        tracking[x_col] = x_filt
        tracking[y_col] = y_filt

        # ── 2. Velocity via central differences ─────────────────────────
        vx = np.gradient(x_filt, dt)
        vy = np.gradient(y_filt, dt)
        speed = np.sqrt(vx ** 2 + vy ** 2)

        # Cap implausible speeds
        too_fast = speed > MAX_PLAYER_SPEED_MS
        vx[too_fast] = np.nan
        vy[too_fast] = np.nan
        speed[too_fast] = np.nan

        # Restore NaN where original positions were NaN
        nan_mask = np.isnan(x_raw) | np.isnan(y_raw)
        vx[nan_mask] = np.nan
        vy[nan_mask] = np.nan
        speed[nan_mask] = np.nan

        tracking[f"{col_id}_vx"] = vx
        tracking[f"{col_id}_vy"] = vy
        tracking[f"{col_id}_velocity"] = speed

        # ── 3. Signed acceleration = d(speed)/dt ───────────────────────
        signed_acc = np.gradient(speed, dt)
        signed_acc[nan_mask] = np.nan
        signed_acc = np.where(
            np.abs(signed_acc) > MAX_SIGNED_ACC_MS2, np.nan, signed_acc
        )

        tracking[f"{col_id}_signed_acceleration"] = signed_acc

    # Also store the magnitude acceleration for compatibility
    # (some DataBallPy internals may expect _acceleration)
    for col_id in column_ids:
        sa_col = f"{col_id}_signed_acceleration"
        if sa_col in tracking.columns:
            tracking[f"{col_id}_acceleration"] = np.abs(
                tracking[sa_col].values
            )

    print(f"    kinematics: done")


def preprocess_game(game) -> None:
    """Preprocess a loaded raw game: ball and player kinematics, playing positions."""
    # Ball: DataBallPy Savitzky-Golay filters (the ball is not used in the analysis)
    game.tracking_data.filter_tracking_data(
        column_ids="ball", filter_type="savitzky_golay",
        window_length=7, polyorder=2,
    )
    game.tracking_data.add_velocity(
        column_ids="ball", max_velocity=50.0,
        filter_type="savitzky_golay", window_length=7, polyorder=2,
    )
    game.tracking_data.add_acceleration(
        column_ids="ball", max_acceleration=20.0,
        filter_type="savitzky_golay", window_length=25, polyorder=2,
    )

    # Players
    apply_player_kinematics(game)

    # Position-specific information
    add_position_specific(game)
