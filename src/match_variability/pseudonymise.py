"""Turn the identified feature table into the shared, pseudonymised table.

What changes (nothing else is touched, every metric value stays identical):
  - ``date``, ``match`` and ``full_name`` are removed;
  - ``team_name`` is replaced by a neutral club code ``team_id`` (T01 to T18);
  - the data provider's ``player_id`` is replaced by a neutral code (P001 ...).

The codes come from two private key files (``player_id_crosswalk.csv`` and
``team_id_crosswalk.csv``). For the manuscript the codes were assigned once at
random (so they carry no information about players, clubs or their order) and
the key files were kept privately. Step 3 reuses those key files, so rerunning
it reproduces the shared table exactly. Only when no key files exist (for new
data) are new random keys made with :func:`make_keys`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DROP_COLUMNS = ["date", "match", "full_name"]


def make_keys(identified: pd.DataFrame, seed: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """New random keys: every player and club gets a code in random order."""
    rng = np.random.default_rng(seed)
    players = rng.permutation(identified["player_id"].drop_duplicates().to_numpy())
    teams = rng.permutation(identified["team_name"].drop_duplicates().to_numpy())
    player_key = pd.DataFrame({
        "player_id_original": players,
        "player_id": [f"P{i:03d}" for i in range(1, len(players) + 1)],
    })
    team_key = pd.DataFrame({
        "team_name": teams,
        "team_id": [f"T{i:02d}" for i in range(1, len(teams) + 1)],
    })
    return player_key, team_key


def pseudonymise(identified: pd.DataFrame, player_key: pd.DataFrame,
                 team_key: pd.DataFrame) -> pd.DataFrame:
    """Apply the keys; fails if any player or club has no code."""
    player_map = dict(zip(player_key["player_id_original"], player_key["player_id"]))
    team_map = dict(zip(team_key["team_name"], team_key["team_id"]))

    out = identified.drop(columns=DROP_COLUMNS)
    out.insert(out.columns.get_loc("team_name"), "team_id", out["team_name"].map(team_map))
    out = out.drop(columns="team_name")
    out["player_id"] = out["player_id"].map(player_map)

    for col in ("team_id", "player_id"):
        if out[col].isna().any():
            raise ValueError(f"{out[col].isna().sum()} rows have no code for {col}: "
                             "the key file does not cover every player/club.")
    return out
