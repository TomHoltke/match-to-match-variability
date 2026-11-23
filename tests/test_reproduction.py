"""Rerun the analysis (steps 4 and 5) in a temporary folder and compare with the shared files.

Passes when every derived data file and every manuscript table is reproduced
exactly. Nothing in the repository is overwritten. Takes about a minute.

    pytest tests/test_reproduction.py
"""

import pandas as pd
import pytest

from match_variability import cleaning, config, manuscript_results

DATA_FILES = ["match_player_features_clean.csv", "player_season_summary.csv",
              "player_season_summary_no_gk.csv"]
TABLES = ["Table1.csv", "TableS1.csv", "TableS2.csv", "TableS3.csv"]


@pytest.fixture(scope="module")
def rerun(tmp_path_factory):
    out = tmp_path_factory.mktemp("rerun")
    mp = pytest.MonkeyPatch()
    mp.setattr(cleaning, "CLEAN_FILE", out / DATA_FILES[0])
    mp.setattr(cleaning, "PLAYER_SUMMARY_FILE", out / DATA_FILES[1])
    mp.setattr(cleaning, "PLAYER_SUMMARY_NO_GK_FILE", out / DATA_FILES[2])
    mp.setattr(manuscript_results, "CLEAN_FILE", out / DATA_FILES[0])
    mp.setattr(manuscript_results, "PLAYER_SUMMARY_FILE", out / DATA_FILES[1])
    mp.setattr(manuscript_results, "OUT", out)
    cleaning.run()
    manuscript_results.run()
    mp.undo()
    return out


@pytest.mark.parametrize("name", DATA_FILES)
def test_derived_data_reproduced(rerun, name):
    shared = pd.read_csv(config.SHARED_DIR / name)
    new = pd.read_csv(rerun / name)
    # Numbers may differ in the last binary digit between machines, never more.
    pd.testing.assert_frame_equal(new, shared, check_exact=False, rtol=1e-12, atol=1e-12)


@pytest.mark.parametrize("name", TABLES)
def test_manuscript_table_reproduced(rerun, name):
    assert (rerun / name).read_text(encoding="utf-8-sig") == \
        (config.RESULTS_DIR / name).read_text(encoding="utf-8-sig")
