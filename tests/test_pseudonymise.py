"""Pseudonymisation on a tiny made-up table (no private data needed)."""

import pandas as pd
import pytest

from match_variability.pseudonymise import make_keys, pseudonymise


@pytest.fixture
def identified():
    return pd.DataFrame({
        "MD": [1, 1, 2], "date": ["2000-01-01"] * 3, "match": ["A vs B"] * 3,
        "team_side": ["home", "away", "home"], "team_name": ["Club A", "Club B", "Club A"],
        "player_id": [111, 222, 111], "full_name": ["Name One", "Name Two", "Name One"],
        "total_distance": [10000.5, 9000.25, 11000.0],
    })


def test_identifying_columns_removed_and_codes_applied(identified):
    pkey, tkey = make_keys(identified, seed=1)
    out = pseudonymise(identified, pkey, tkey)
    assert list(out.columns) == ["MD", "team_side", "team_id", "player_id", "total_distance"]
    assert set(out["player_id"]) <= set(pkey["player_id"])
    assert set(out["team_id"]) <= set(tkey["team_id"])
    assert out["player_id"].iloc[0] == out["player_id"].iloc[2]          # same player, same code
    assert out["total_distance"].tolist() == identified["total_distance"].tolist()


def test_missing_key_fails(identified):
    pkey, tkey = make_keys(identified, seed=1)
    with pytest.raises(ValueError):
        pseudonymise(identified, pkey.iloc[:1], tkey)
