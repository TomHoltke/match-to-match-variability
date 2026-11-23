"""
match_features.py
=================

Combines ALL per-player features into one unified DataFrame for a single game.

Metrics included
----------------
  Covered distance (DataBallPy get_covered_distance):
      total_distance, walking_distance, jogging_distance,
      running_distance, high_speed_running_distance, sprinting_distance

  Change of Direction  (change_of_direction.py)
  Acceleration / Decel (acceleration_deceleration.py)
  Sprint               (sprint.py)

  Every raw count / distance column that arrives from a child script gets
  a corresponding ``_per_90`` column added here (raw value / playing_duration
  × 90).  The child scripts' own ``_per_min`` columns are dropped on merge
  so there is no duplication.

  Per-effort means (mean_sprint_dist_m, mean_sprint_duration_s, etc.) and
  absolute speeds (mean_peak_speed_ms, max_peak_speed_ms) are NOT
  normalised — they are already effort-level averages, not match totals.

Auto-update behaviour
---------------------
The builder does NOT maintain a hardcoded column list for child-script
output.  It strips only the metadata columns that would duplicate what
comes from the main player table (full_name, side, shirt_num, position,
playing_min, any *_per_min columns).  Every other column produced by a
child script — including any new ones you add in the future — flows
through automatically and lands after the fixed metadata block.

Speed
-----
The bottleneck is game loading, not feature extraction.  The four feature
functions run sequentially because they share the tracking DataFrame in
memory; parallelising them would require re-loading the game per process,
which is slower.  No meaningful speedup is available in the builder itself.

Sanity checks
-------------
Only a short one-line summary is printed (n flags / n warnings).
The full list is returned so it can be logged during batch processing.

Public entry point
------------------
    build_player_match_features(game, saved_game_name) -> (pd.DataFrame, list[str])
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from match_variability.tracking.acceleration_deceleration import compute_acc_dec_features
from match_variability.tracking.change_of_direction import compute_cod_features
from match_variability.tracking.sprint import compute_sprint_features


# =============================================================================
# Constants
# =============================================================================
_VELOCITY_INTERVALS = ((0, 2), (2, 4), (4, 5.5), (5.5, 7), (7, np.inf))
_DIST_COLS = [
    "total_distance",
    "walking_distance",
    "jogging_distance",
    "running_distance",
    "high_speed_running_distance",
    "sprinting_distance",
]

# Columns that child scripts carry as metadata — drop to avoid duplication.
_CHILD_META_DROP = {"full_name", "side", "shirt_num", "position", "playing_min"}

# Per-effort / absolute-speed columns that must NOT get a _per_90 version.
_NO_PER_90 = {
    # Per-effort means (sprint)
    "mean_sprint_dist_m",
    "mean_sprint_duration_s",
    "mean_peak_speed_ms",
    "max_peak_speed_ms",
    # Match-level peaks (speed, acc, dec) — magnitudes, not totals
    "peak_speed_ms",
    "peak_acc_ms2",
    "peak_dec_ms2",
    # Per-event mean magnitudes (acc/dec) — means, not totals
    "mean_acc_magnitude_ms2",
    "mean_dec_magnitude_ms2",
    # n_acc_SP zone components — normalise only the total (n_acc_SP)
    "n_hi_acc_standing",
    "n_hi_acc_trotting",
    "n_hi_acc_jogging",
    "n_hi_acc_running",
}

# Fixed metadata columns — always first in output.
_META_COLS = [
    "MD", "date", "match",
    "team_side", "team_name", "player_id", "full_name",
    "shirt_num", "starter", "position_specific", "column_id",
    "playing_duration",
]

# Sanity check reference ranges (per 90 min).
_RANGES_PER_90: dict[str, tuple[float, float]] = {
    "total_distance":              (8_000,  15_000),
    "sprinting_distance":          (100,     500),
    "high_speed_running_distance": (500,    2_500),
    "CoD_total":                   (20,      350),
    "n_acc_3":                     (10,      200),
    "n_dec_3":                     (10,      200),
    "n_acc_SP":                    (5,       150),
    "n_sprints":                   (5,        60),
    "sprint_distance_m":           (50,      600),
    "mean_peak_speed_ms":          (7.0,     11.5),
    "max_peak_speed_ms":           (7.0,     12.0),
    "peak_speed_ms":               (6.0,     12.0),
    "peak_acc_ms2":                (2.0,     10.0),
    "peak_dec_ms2":                (2.0,     10.0),
    "mean_acc_magnitude_ms2":      (3.0,      7.0),
    "mean_dec_magnitude_ms2":      (3.0,      7.0),
}
_MIN_MIN_FOR_CHECK = 20.0

# Raw columns whose sanity range should NOT be scaled by playing time
# (magnitudes / peaks, not cumulative totals).
_NO_SCALE_RANGES = {
    "mean_peak_speed_ms",
    "max_peak_speed_ms",
    "peak_speed_ms",
    "peak_acc_ms2",
    "peak_dec_ms2",
    "mean_acc_magnitude_ms2",
    "mean_dec_magnitude_ms2",
}


# =============================================================================
# Helpers
# =============================================================================
def _parse_md(name: str) -> int:
    m = re.search(r"\bMD\s*([0-9]{1,2})\b", str(name), flags=re.IGNORECASE)
    if not m:
        raise ValueError(f"Cannot parse matchday from '{name}'")
    return int(m.group(1))


def _match_date(game) -> str:
    dt = pd.to_datetime(getattr(game, "date", pd.NaT))
    return "" if pd.isna(dt) else dt.date().isoformat()


def _match_label(game) -> str:
    date = _match_date(game)
    home = getattr(game, "home_team_name", "Home")
    away = getattr(game, "away_team_name", "Away")
    return f"{date} - {home} vs {away}"


def _safe_div(a: pd.Series, b: pd.Series) -> pd.Series:
    return a / b.where((b > 0) & b.notna(), np.nan)


# =============================================================================
# Covered distance
# =============================================================================
def _get_covered_distance(game) -> pd.DataFrame:
    cd = game.tracking_data.get_covered_distance(
        column_ids=game.get_column_ids(),
        velocity_intervals=_VELOCITY_INTERVALS,
    )
    cd.columns = _DIST_COLS
    return cd


def _get_playing_duration(game) -> pd.Series:
    tracking = (game.tracking_data.data
                if hasattr(game.tracking_data, "data")
                else game.tracking_data)
    fps = game.tracking_data.frame_rate
    td  = tracking[tracking["period_id"].isin([1, 2])]
    out = {}
    for col_id in game.get_column_ids():
        v_col = f"{col_id}_velocity"
        if v_col not in td.columns:
            out[col_id] = np.nan
        else:
            n = int(td[v_col].notna().sum())
            out[col_id] = min((n / fps) / 60.0, 105.0)
    return pd.Series(out, name="playing_duration")


# =============================================================================
# Player metadata
# =============================================================================
def _player_metadata(game, active_ids: set) -> pd.DataFrame:
    rows = []
    for side in ("home", "away"):
        team_name = getattr(game, f"{side}_team_name", side)
        for _, p in getattr(game, f"{side}_players").iterrows():
            shirt = p["shirt_num"]
            if pd.isna(shirt):
                continue
            col_id = f"{side}_{int(shirt)}"
            if col_id not in active_ids:
                continue
            starter = bool(p.get("starter", False))
            pos = str(p.get("position_specific", "unknown") or "unknown").strip() or "unknown"
            if not starter:
                pos = "unknown"
            rows.append({
                "team_side":         side,
                "team_name":         team_name,
                "player_id":         p["id"],
                "full_name":         p["full_name"],
                "shirt_num":         int(shirt),
                "starter":           starter,
                "position_specific": pos,
                "column_id":         col_id,
            })
    return pd.DataFrame(rows)


# =============================================================================
# Per-90 normalisation
# =============================================================================
def _add_per_90(df: pd.DataFrame) -> pd.DataFrame:
    """
    For every numeric column that is not in _META_COLS and not in _NO_PER_90,
    add a ``<col>_per_90`` column immediately after it.
    Skips columns that already end in ``_per_90`` or ``_per_min``.
    """
    dur = df["playing_duration"]
    insert_pairs: list[tuple[int, str, pd.Series]] = []

    for i, col in enumerate(df.columns):
        if col in _META_COLS:
            continue
        if col.endswith(("_per_90", "_per_min")):
            continue
        if col in _NO_PER_90:
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue
        name_90 = f"{col}_per_90"
        val_90  = _safe_div(df[col] * 90.0, dur).round(2)
        insert_pairs.append((i + 1, name_90, val_90))

    # Insert in reverse order to keep position indices valid.
    result = df.copy()
    for pos, name, series in reversed(insert_pairs):
        result.insert(pos, name, series)

    return result


# =============================================================================
# Sanity checks  (quiet — only summary line printed)
# =============================================================================
def _sanity_check(df: pd.DataFrame) -> list[str]:
    messages: list[str] = []

    def _flag(msg: str):
        messages.append(f"FLAG    | {msg}")

    def _warn(msg: str):
        messages.append(f"WARNING | {msg}")

    # 1. Playing time bounds
    if "playing_duration" in df.columns:
        for _, r in df[df["playing_duration"] > 105].iterrows():
            _flag(f"{r['column_id']}  playing_duration={r['playing_duration']:.1f} min > 105")
        n_zero = (df["playing_duration"] <= 0).sum()
        if n_zero:
            _warn(f"{n_zero} player(s) with playing_duration <= 0")

    # 2. Literature-range checks on _per_90 columns (only players >= _MIN_MIN_FOR_CHECK)
    check = df[df.get("playing_duration", pd.Series(999, index=df.index)) >= _MIN_MIN_FOR_CHECK]
    for raw_col, (lo90, hi90) in _RANGES_PER_90.items():
        p90_col = f"{raw_col}_per_90"
        col = p90_col if p90_col in check.columns else (raw_col if raw_col in check.columns else None)
        if col is None:
            continue
        # For raw cols scale the limit; for _per_90 use limit directly.
        # Peaks/magnitudes (in _NO_SCALE_RANGES) are NOT scaled by playing time.
        if (col == raw_col
                and raw_col not in _NO_SCALE_RANGES
                and "playing_duration" in check.columns):
            scale = check["playing_duration"] / 90.0
            lo_eff, hi_eff = lo90 * scale, hi90 * scale
        else:
            lo_eff, hi_eff = lo90, hi90

        for _, r in check[check[col] < lo_eff].iterrows():
            eff = lo_eff[r.name] if hasattr(lo_eff, "__getitem__") else lo_eff
            _warn(f"{r['column_id']}  {col}={r[col]:.1f} < expected {eff:.1f}/90 min")
        for _, r in check[check[col] > hi_eff].iterrows():
            eff = hi_eff[r.name] if hasattr(hi_eff, "__getitem__") else hi_eff
            _flag(f"{r['column_id']}  {col}={r[col]:.1f} > expected {eff:.1f}/90 min")

    # 3. n_acc_SP zone sum
    zone_cols = ["n_hi_acc_standing", "n_hi_acc_trotting",
                 "n_hi_acc_jogging",  "n_hi_acc_running"]
    if "n_acc_SP" in df.columns and all(c in df.columns for c in zone_cols):
        bad = df[df[zone_cols].sum(axis=1) != df["n_acc_SP"]]
        if not bad.empty:
            _flag(f"n_acc_SP zone-sum mismatch: {bad['column_id'].tolist()}")

    # 4. CoD_total = Low + Medium + High
    if all(c in df.columns for c in ["CoD_low", "CoD_medium", "CoD_high", "CoD_total"]):
        bad = df[df[["CoD_low", "CoD_medium", "CoD_high"]].sum(axis=1) != df["CoD_total"]]
        if not bad.empty:
            _flag(f"CoD_total mismatch: {bad['column_id'].tolist()}")

    # 5. max_peak_speed >= mean_peak_speed
    if {"max_peak_speed_ms", "mean_peak_speed_ms"}.issubset(df.columns):
        bad = df[(df["n_sprints"] > 0) & (df["max_peak_speed_ms"] < df["mean_peak_speed_ms"])]
        if not bad.empty:
            _flag(f"max_peak_speed < mean_peak_speed: {bad['column_id'].tolist()}")

    # 6. Match-level peak speed must be >= max peak speed across sprint efforts.
    if {"peak_speed_ms", "max_peak_speed_ms"}.issubset(df.columns):
        bad = df[(df["n_sprints"] > 0) & (df["peak_speed_ms"] < df["max_peak_speed_ms"])]
        if not bad.empty:
            _flag(f"peak_speed_ms < max_peak_speed_ms: {bad['column_id'].tolist()}")

    # --- summary (one line) ---
    n_flags = sum(1 for m in messages if m.startswith("FLAG"))
    n_warns = sum(1 for m in messages if m.startswith("WARNING"))
    if messages:
        print(f"  sanity: {n_flags} flag(s), {n_warns} warning(s)  "
              f"— call get_issues() or inspect the returned list for details")
    else:
        print("  sanity: ✓ all checks passed")

    return messages


# =============================================================================
# Main builder
# =============================================================================
def build_player_match_features(
    game,
    saved_game_name: str,
) -> tuple[pd.DataFrame, list[str]]:
    """Build a unified per-player feature DataFrame for one game.

    Parameters
    ----------
    game             : DataBallPy game object (output of get_saved_game).
    saved_game_name  : folder name of the game — used to parse matchday (MD).

    Returns
    -------
    df       : pd.DataFrame, one row per player.
               Column layout:
                 metadata  →  playing_duration
                 →  distance (raw + _per_90)
                 →  CoD     (raw + CoD_total_per_90)
                 →  AccDec  (raw + _per_90 where applicable)
                 →  Sprint  (raw + _per_90 where applicable)
               Any new columns added to child scripts appear automatically.
    messages : list[str] of sanity-check issues ("FLAG | ..." / "WARNING | ...").
    """
    print(f"  Building features: {game.home_team_name} vs {game.away_team_name} "
          f"({saved_game_name})", flush=True)

    MD       = _parse_md(saved_game_name)
    date_str = _match_date(game)
    match    = _match_label(game)

    # ── 1. Covered distance ───────────────────────────────────────────
    print("    [1/4] covered distance …", end=" ", flush=True)
    cd  = _get_covered_distance(game)
    dur = _get_playing_duration(game)
    cd["playing_duration"] = dur
    active_ids = set(cd.index.astype(str))
    print(f"OK ({len(active_ids)} players)")

    # ── 2. CoD ───────────────────────────────────────────────────────
    print("    [2/4] CoD …", end=" ", flush=True)
    cod = compute_cod_features(game)
    print(f"OK ({len(cod)} players)")

    # ── 3. Acc / Dec ─────────────────────────────────────────────────
    print("    [3/4] Acc/Dec …", end=" ", flush=True)
    accdec = compute_acc_dec_features(game)
    print(f"OK ({len(accdec)} players)")

    # ── 4. Sprint ────────────────────────────────────────────────────
    print("    [4/4] Sprint …", end=" ", flush=True)
    spr = compute_sprint_features(game)
    print(f"OK ({len(spr)} players)")

    # ── Prepare child frames for merge ───────────────────────────────
    # Drop metadata columns that duplicate the main player table, and also
    # any _per_min columns — the builder owns all normalisation via _per_90.
    def _prep(child: pd.DataFrame) -> pd.DataFrame:
        child = child.rename(columns={"player_column_id": "column_id"})
        drop = [c for c in child.columns
                if c in _CHILD_META_DROP or c.endswith("_per_min")]
        return child.drop(columns=drop, errors="ignore")

    # ── Merge ────────────────────────────────────────────────────────
    meta     = _player_metadata(game, active_ids)
    cd_reset = cd.reset_index().rename(columns={"index": "column_id"})

    df = (
        meta
        .merge(cd_reset,       on="column_id", how="inner")
        .merge(_prep(cod),     on="column_id", how="left")
        .merge(_prep(accdec),  on="column_id", how="left")
        .merge(_prep(spr),     on="column_id", how="left")
    )

    # ── Match metadata at the front ──────────────────────────────────
    df.insert(0, "MD",    MD)
    df.insert(1, "date",  date_str)
    df.insert(2, "match", match)

    # ── Add _per_90 columns next to each raw column ──────────────────
    df = _add_per_90(df)

    # ── Ensure metadata block is always first ────────────────────────
    meta_present = [c for c in _META_COLS if c in df.columns]
    rest         = [c for c in df.columns if c not in meta_present]
    df = df[meta_present + rest]

    # ── Sort: home starters → home subs → away starters → away subs ─
    df["team_side"] = pd.Categorical(df["team_side"], ["home", "away"], ordered=True)
    df = (
        df.sort_values(["team_side", "starter", "shirt_num"],
                       ascending=[True, False, True], kind="mergesort")
          .reset_index(drop=True)
    )

    # ── Round all numeric columns to 2 dp ───────────────────────────
    num = df.select_dtypes(include=[np.number]).columns
    df[num] = df[num].round(2)

    print(f"    → {df.shape[0]} players × {df.shape[1]} columns")

    # ── Sanity checks ────────────────────────────────────────────────
    messages = _sanity_check(df)

    return df, messages
