"""Step 3: identified feature table -> shared, pseudonymised feature table.

Needs the private feature table (step 2) and the private key files. Not
needed to reproduce the manuscript results.

Reads  : IDENTIFIED_FEATURES_FILE, PLAYER_KEY_FILE, TEAM_KEY_FILE
Writes : data/shared/match_player_features.csv   (the shared input of step 4)

Removes date, match and player names and replaces player and club ids by
neutral codes (see src/match_variability/pseudonymise.py). The existing key
files are reused, so the shared table is reproduced exactly. New random keys
are made only when no key files exist yet.

Run from the repository root:
    python scripts/1_tracking_pipeline/s03_pseudonymise.py
"""

from __future__ import annotations

import pandas as pd

from match_variability.config import (
    IDENTIFIED_FEATURES_FILE,
    MATCH_FEATURES_FILE,
    PLAYER_KEY_FILE,
    TEAM_KEY_FILE,
)
from match_variability.pseudonymise import make_keys, pseudonymise


def main() -> None:
    identified = pd.read_parquet(IDENTIFIED_FEATURES_FILE)

    if PLAYER_KEY_FILE.exists() and TEAM_KEY_FILE.exists():
        player_key, team_key = pd.read_csv(PLAYER_KEY_FILE), pd.read_csv(TEAM_KEY_FILE)
        print(f"Using existing keys: {len(player_key)} players, {len(team_key)} clubs")
    elif PLAYER_KEY_FILE.exists() or TEAM_KEY_FILE.exists():
        raise SystemExit("Only one of the two key files exists; restore the other one first.")
    else:
        player_key, team_key = make_keys(identified)
        PLAYER_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        player_key.to_csv(PLAYER_KEY_FILE, index=False)
        team_key.to_csv(TEAM_KEY_FILE, index=False)
        print(f"No keys found: made new random keys in {PLAYER_KEY_FILE.parent}")

    shared = pseudonymise(identified, player_key, team_key)
    MATCH_FEATURES_FILE.parent.mkdir(parents=True, exist_ok=True)
    shared.to_csv(MATCH_FEATURES_FILE, index=False)
    print(f"Saved {shared.shape[0]:,} rows x {shared.shape[1]} columns -> {MATCH_FEATURES_FILE}")


if __name__ == "__main__":
    main()
