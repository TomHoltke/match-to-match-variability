"""Step 1: raw tracking data -> one preprocessed saved game per match.

Needs the private raw data and the optional ``tracking`` dependencies. Not
needed to reproduce the manuscript results (start at step 4 for that).

Reads  : RAW_TRACKING_DIR, per match four files with the same stem:
             <stem>.dat, <stem> metadata.xml   (TRACAB tracking, 25 Hz)
             <stem> f7.xml                      (Opta line-ups: formation)
             <stem> f24.xml                     (Opta events: read by DataBallPy
                                                 with the line-ups, not used)
         MATCH_LIST_FILE: which matches to process (included = 1), and the
             name of each saved game (it carries the matchday as "MDxx")
Writes : SAVED_GAMES_DIR/<saved_game_name>/   (DataBallPy saved game)

Per match: load with DataBallPy, filter positions and compute speed and
signed acceleration (tracking/kinematics.py), add the playing position of
every starter (tracking/positions.py), save.

Run from the repository root:
    python scripts/1_tracking_pipeline/s01_raw_to_saved_games.py
    python scripts/1_tracking_pipeline/s01_raw_to_saved_games.py --only "<saved_game_name>"

Existing saved games are skipped unless --overwrite is given.
"""

from __future__ import annotations

import argparse
import traceback
from pathlib import Path

import pandas as pd
from databallpy import get_game

from match_variability.config import MATCH_LIST_FILE, RAW_TRACKING_DIR, SAVED_GAMES_DIR
from match_variability.tracking.kinematics import preprocess_game


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="process only this saved_game_name")
    parser.add_argument("--overwrite", action="store_true", help="replace existing saved games")
    parser.add_argument("--output-dir", type=Path, default=SAVED_GAMES_DIR,
                        help=f"where to save (default: {SAVED_GAMES_DIR})")
    args = parser.parse_args()

    matches = pd.read_csv(MATCH_LIST_FILE)
    matches = matches[matches["included"] == 1]
    if args.only:
        matches = matches[matches["saved_game_name"] == args.only]
        if matches.empty:
            raise SystemExit(f"'{args.only}' is not an included match in {MATCH_LIST_FILE}")

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    done = skipped = failed = 0
    for i, m in enumerate(matches.itertuples(), 1):
        stem, name = m.raw_stem, m.saved_game_name
        print(f"[{i}/{len(matches)}] {name}")
        if (out_dir / name).exists() and not args.overwrite:
            print("  exists, skipped")
            skipped += 1
            continue
        try:
            game = get_game(
                tracking_data_loc=str(RAW_TRACKING_DIR / f"{stem}.dat"),
                tracking_metadata_loc=str(RAW_TRACKING_DIR / f"{stem} metadata.xml"),
                tracking_data_provider="tracab",
                event_data_loc=str(RAW_TRACKING_DIR / f"{stem} f24.xml"),
                event_metadata_loc=str(RAW_TRACKING_DIR / f"{stem} f7.xml"),
                event_data_provider="opta",
            )
            preprocess_game(game)
            game.save_game(name=name, path=str(out_dir), allow_overwrite=args.overwrite)
            done += 1
        except Exception as e:  # keep going, report at the end
            failed += 1
            print(f"  FAILED: {e!r}")
            traceback.print_exc()

    print(f"\nDone: {done} saved, {skipped} skipped (exist), {failed} failed.")


if __name__ == "__main__":
    main()
