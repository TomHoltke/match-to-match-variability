"""Step 2: saved games -> identified feature table (one row per player per match).

Needs the private saved games (step 1) and the optional ``tracking``
dependencies. Not needed to reproduce the manuscript results.

Reads  : SAVED_GAMES_DIR/<saved_game_name>/ for every included match in MATCH_LIST_FILE
Writes : IDENTIFIED_FEATURES_FILE (parquet, private: still has names and provider ids)

Per match, tracking/match_features.py computes playing time, covered distance
per speed zone, change of direction, acceleration/deceleration and sprint
metrics, plus a per-90 version of every count and distance.

Run from the repository root:
    python scripts/1_tracking_pipeline/s02_extract_match_features.py
    python scripts/1_tracking_pipeline/s02_extract_match_features.py --only "<saved_game_name>" --output check.parquet

The existing feature table is never overwritten unless --overwrite is given.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd
from databallpy import get_saved_game

from match_variability.config import IDENTIFIED_FEATURES_FILE, MATCH_LIST_FILE, SAVED_GAMES_DIR
from match_variability.tracking.match_features import build_player_match_features


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="process only this saved_game_name")
    parser.add_argument("--output", type=Path, default=IDENTIFIED_FEATURES_FILE,
                        help=f"output parquet file (default: {IDENTIFIED_FEATURES_FILE})")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing output file")
    parser.add_argument("--saved-games-dir", type=Path, default=SAVED_GAMES_DIR,
                        help=f"where the saved games are (default: {SAVED_GAMES_DIR})")
    args = parser.parse_args()

    if args.output.exists() and not args.overwrite:
        raise SystemExit(f"{args.output} exists. Use --overwrite or --output <other file>.")

    matches = pd.read_csv(MATCH_LIST_FILE)
    names = sorted(matches.loc[matches["included"] == 1, "saved_game_name"])
    if args.only:
        names = [n for n in names if n == args.only]
        if not names:
            raise SystemExit(f"'{args.only}' is not an included match in {MATCH_LIST_FILE}")

    frames, failed, n_issue_games = [], [], 0
    t0 = time.time()
    for i, name in enumerate(names, 1):
        print(f"[{i}/{len(names)}] {name}")
        try:
            game = get_saved_game(name=name, path=str(args.saved_games_dir))
            df, issues = build_player_match_features(game, name)
            frames.append(df)
            n_issue_games += bool(issues)
            eta = (time.time() - t0) / i * (len(names) - i) / 60
            print(f"    {len(df)} players | ETA {eta:.1f} min")
        except Exception as e:  # keep going, report at the end
            failed.append((name, repr(e)))
            print(f"    FAILED: {e!r}")

    if not frames:
        raise SystemExit("No match processed successfully.")
    master = pd.concat(frames, ignore_index=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    master.to_parquet(args.output, index=False, engine="pyarrow")

    print(f"\nSaved {master.shape[0]:,} rows x {master.shape[1]} columns "
          f"({master['match'].nunique()} matches) -> {args.output}")
    print(f"Sanity-check messages in {n_issue_games} match(es); {len(failed)} failed.")
    for name, err in failed:
        print(f"  FAILED {name}: {err}")


if __name__ == "__main__":
    main()
