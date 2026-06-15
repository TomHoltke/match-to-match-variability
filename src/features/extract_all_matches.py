"""
extract_all_matches.py  (reference only — requires raw tracking data)
=====================================================================

Batch-process every saved tracking game and build one master table with all
per-player features (covered distance, change of direction, acceleration /
deceleration, sprint) plus per-match metadata.

This is the step that produced the feature export behind the shared
``data/match_player_features.xlsx`` distributed with this repository. The raw
tracking games are NOT shared, so this script cannot be run from the public
repository — it is included purely to document how the shared feature table was
generated.

Usage (data owner only, with raw games available)
-------------------------------------------------
    python -m src.features.extract_all_matches
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.config import DATA_DIR
from src.features.build_match_features import build_player_match_features
from databallpy import get_saved_game

# --------------------------------------------------------------------------- #
# Config — fill in with a local path to the saved tracking games.
# --------------------------------------------------------------------------- #
GAMES_FOLDER = "<path/to/saved/tracking/games>"
# Raw (identifying) export; git-ignored, lives only on the data owner's machine.
OUTPUT_STEM = DATA_DIR / "_private_raw_features"


def process_all_games(games_folder: str = GAMES_FOLDER) -> pd.DataFrame | None:
    print("=" * 70)
    print("  FULL FEATURE BATCH PROCESSING")
    print(f"  Start: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 70)

    games_path = Path(games_folder)
    game_folders = sorted(
        d for d in games_path.iterdir() if d.is_dir() and "MD" in d.name
    )
    total = len(game_folders)
    print(f"  Found {total} game folders\n")
    if total == 0:
        print("  ERROR: no game folders found.")
        return None

    all_dfs: list[pd.DataFrame] = []
    all_issues: list[tuple[str, list[str]]] = []
    successful = failed = 0
    failed_games: list[tuple[str, str]] = []
    t0 = time.time()

    for idx, folder in enumerate(game_folders, 1):
        name = folder.name
        print(f"\n[{idx}/{total}] {name}")
        try:
            game = get_saved_game(name=name, path=games_folder)
            df, issues = build_player_match_features(game, name)
            all_dfs.append(df)
            if issues:
                all_issues.append((name, issues))
            successful += 1
            elapsed = time.time() - t0
            eta = (elapsed / idx) * (total - idx) / 60.0
            print(f"    ✓ {len(df)} players  |  elapsed {elapsed/60:.1f} min  |  ETA {eta:.1f} min")
        except Exception as e:
            failed += 1
            failed_games.append((name, str(e)))
            print(f"    ✗ FAILED: {e}")

    print("\n" + "=" * 70)
    print("  COMBINING DATA")
    print("=" * 70)
    if not all_dfs:
        print("  ERROR: zero games processed successfully.")
        return None

    master = pd.concat(all_dfs, ignore_index=True)
    print(f"  Shape: {master.shape[0]:,} rows × {master.shape[1]} columns")
    print(f"  Unique matches:  {master['match'].nunique()}")
    print(f"  Unique players:  {master['player_id'].nunique()}")
    print(f"  Match rounds:    {sorted(master['MD'].unique())}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    parquet_path = OUTPUT_STEM.with_suffix(".parquet")
    xlsx_path = OUTPUT_STEM.with_suffix(".xlsx")
    print(f"\n  Saving parquet → {parquet_path}")
    master.to_parquet(parquet_path, index=False, engine="pyarrow")
    print(f"  Saving xlsx    → {xlsx_path}")
    master.to_excel(xlsx_path, index=False, engine="openpyxl")

    total_time = time.time() - t0
    print(f"\n{'=' * 70}")
    print(f"  DONE — {successful}/{total} games  |  {failed} failed  |  {total_time/60:.1f} min total")
    print(f"  End: {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"{'=' * 70}")

    if failed_games:
        print(f"\n  Failed games ({failed}):")
        for g, e in failed_games:
            print(f"    - {g}: {e}")

    if all_issues:
        n_flags = sum(sum(1 for m in msgs if m.startswith("FLAG")) for _, msgs in all_issues)
        n_warns = sum(sum(1 for m in msgs if m.startswith("WARNING")) for _, msgs in all_issues)
        print(f"\n  Sanity issues across all games: {n_flags} flag(s), {n_warns} warning(s)")
        print(f"  Games with issues: {len(all_issues)}/{successful}")

    return master


if __name__ == "__main__":
    process_all_games()
