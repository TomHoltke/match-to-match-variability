# Match-to-match variability of physical-demand metrics in professional football

Code and data to reproduce every table and figure of the manuscript on
**within-player, match-to-match variability (coefficient of variation, CV%)**
of 19 physical-match load metrics from optical tracking data, and how that
variability differs between playing positions.

**In short:** install the packages, run two scripts, and the results in
`results/manuscript/` are regenerated from the shared data in `data/shared/`.
A test checks that your rerun matches the shared results exactly.

---

## 1. Quick start (about 5 minutes)

You need **Python 3.12** ([python.org](https://www.python.org/downloads/)) and,
optionally, git. Run all commands from the repository folder.

```bash
# 1. Get the code (or download the ZIP from GitHub and unzip it)
git clone https://github.com/TomHoltke/match-to-match-variability.git
cd match-to-match-variability

# 2. Make an isolated Python environment and install the exact package versions
python3.12 -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Run the analysis
python scripts/2_analysis/s04_clean_and_summarise.py
python scripts/2_analysis/s05_manuscript_results.py

# 4. Check that you got the same results
pytest
```

`pytest` reruns the analysis in a temporary folder and compares every derived
data file and every manuscript table with the shared ones. **All tests passing
means you reproduced the manuscript results exactly.** If you used git, `git
status` after step 3 should also list no changed files.

Poetry users can replace step 2 with `poetry install` (same versions, from
`poetry.lock`) and prefix the commands with `poetry run`.

`ModuleNotFoundError: No module named 'match_variability'` means the environment
is not active: run the `activate` line of step 2 again in each new terminal
(the installation itself stays).

---

## 2. What reproduces what

| Manuscript | File in `results/manuscript/` | Made by |
|---|---|---|
| Results, first paragraph (cohort: 146 players, 3,458 player-match observations, 280 matches, matches per player, playing time) | printed to the screen | `s05_manuscript_results.py` |
| **Table 1**: CV% per metric, difference vs total distance | `Table1.csv` | `s05_manuscript_results.py` |
| **Figure 1**: position contrasts vs central midfielders | `Figure1_forest_position_vs_CM.png` | `s05_manuscript_results.py` |
| **Table S1**: descriptives and CV% per position | `TableS1.csv` | `s05_manuscript_results.py` |
| **Table S2**: mixed-model fit and likelihood-ratio tests | `TableS2.csv` | `s05_manuscript_results.py` |
| **Table S3**: Tukey contrasts per metric (the numbers in Figure 1) | `TableS3.csv` | `s05_manuscript_results.py` |
| All of the above, formatted as in the manuscript | `Manuscript_tables_and_figure.docx` | `s05_manuscript_results.py` |
| Full statistical output, unrounded: cohort, all descriptives (overall and per position), complete output of every mixed model, likelihood-ratio tests, all Tukey pairs (also printed to the screen) | `Statistical_output.txt` | `s05_manuscript_results.py` |

The CSV tables open in Excel and hold exactly the text shown in the manuscript
tables.

---

## 3. Repository layout

```
.
├── data/shared/                       the shared data (pseudonymised, see section 5)
│   ├── match_player_features.csv          INPUT: one row per player per match
│   ├── match_player_features_clean.csv    made by step 4: matches of eligible players
│   ├── player_season_summary.csv          made by step 4: one row per player (mean, SD, CV%)
│   └── player_season_summary_no_gk.csv    made by step 4: the same without goalkeepers
├── results/manuscript/                tables, figure and Word file (made by step 5)
├── scripts/
│   ├── 1_tracking_pipeline/           steps 1 to 3: raw tracking data -> shared input
│   │   ├── s01_raw_to_saved_games.py      (need the raw data, which is not shared;
│   │   ├── s02_extract_match_features.py   see section 6)
│   │   └── s03_pseudonymise.py
│   └── 2_analysis/                    steps 4 and 5: shared input -> manuscript results
│       ├── s04_clean_and_summarise.py
│       └── s05_manuscript_results.py
├── src/match_variability/             all the logic (the scripts only call it)
│   ├── config.py                          all paths, inclusion thresholds, position groups
│   ├── cleaning.py                        step 4: cohort selection, per-player mean/SD/CV%
│   ├── manuscript_results.py              step 5: mixed models, Tukey tests, tables, figure
│   ├── pseudonymise.py                    step 3: names and ids -> neutral codes
│   └── tracking/                          steps 1 and 2: filtering, positions, all 19 metrics
├── tests/                             reproduction test and pseudonymisation tests
├── docs/
│   ├── data_dictionary.md                 every column of the shared data
│   └── tracking_pipeline.md               steps 1 to 3 in detail (raw data -> shared input)
├── config/paths.example.toml          only for the tracking pipeline (private data paths)
├── CHANGELOG.md                       what changed between versions of this repository
├── requirements.txt                   exact package versions (pip)
└── pyproject.toml, poetry.lock        the same for Poetry
```

---

## 4. The analysis step by step (steps 4 and 5)

### Step 4: cohort and per-player CV% (`src/match_variability/cleaning.py`)

1. **Eligible matches and players.** A match counts when the player played at
   least 60 min; a player is included with at least 17 such matches (half of
   the 34 matchdays). Thresholds: `MIN_MINUTES`, `MIN_MATCHES` in `config.py`.
   This gives 165 players (148 without goalkeepers).
2. **Per-player season values.** For every metric, the mean and SD over the
   player's eligible matches and **CV% = 100 × SD / mean**. One CV% per player
   per metric.
3. **Position group.** Detailed positions (from the starting formation) are
   grouped (`POSITION_GROUP_MAP` in `config.py`); a player's group is the one
   played in most eligible matches.

### Step 5: models, tests, tables and figure (`src/match_variability/manuscript_results.py`)

1. **Analysis cohort**: players in the five position groups CM, CB, FB, AM, CF
   (`ANALYSIS_POSITIONS`): **146 players**. Goalkeepers (17) and the two players
   whose primary group was wide midfielder or winger (one each) are not modelled.
2. **19 metrics**: the `METRICS` list at the top of the file maps each data
   column to its label in the tables and figure. Counts and distances are per
   90 min; magnitudes and peaks are not.
3. **Linear mixed-effects models** (statsmodels `mixedlm`, random intercept per
   player, 146 × 19 = 2,774 CV% values):
   - M1: `CV% ~ Metric`; M2: `+ Position`; M3: `+ Metric × Position`.
   - Reference categories: total distance (Metric) and CM (Position).
   - Coefficients, 95% CI, p-values, variance components and ICC from REML fits
     (Table 1, Table S2).
   - Log-likelihoods and likelihood-ratio tests from maximum-likelihood (ML) fits
     of the same models, because REML likelihoods cannot be compared between
     models with different fixed effects (Table S2).
4. **Position differences per metric**: one-way Tukey HSD across the five
   positions within each metric (family-wise α = 0.05 over the ten pairs);
   the four contrasts against CM are reported (Table S3) and plotted (Figure 1)
   from the same calculation.

---

## 5. The shared data

`data/shared/match_player_features.csv` is the input of the analysis: **8,584
rows**, one per player per match, for **515 players, 18 clubs and 280 matches**
of one season of a European top-tier league, with the 19 metrics plus related
ones (raw value and per-90 value). Every column is described in
[`docs/data_dictionary.md`](docs/data_dictionary.md). The other three files in
`data/shared/` are made from it by step 4 and are included for convenience.

**Privacy.** The shared data contain no names, dates, match names, shirt
numbers, competition or season (matchday and home/away are kept). Clubs and players appear only as neutral codes (`T01` to `T18`, `P001`
to `P515`) that were assigned at random. The key that links codes to real
clubs and players is kept privately by the authors and is not part of this
repository.

---

## 6. From raw tracking data to the shared input (steps 1 to 3)

The shared input was made from the raw optical tracking data (TRACAB, 25 Hz)
with the code in `scripts/1_tracking_pipeline/` and
`src/match_variability/tracking/`. **The raw data cannot be shared** (licensed
from the data provider, and identifiable). No event data were used: the only
other input is the line-up file (Opta f7), for each starter's position in the
starting formation. The code is included so that every
processing step is open to inspection, and so that the complete pipeline can be
rerun on request by anyone who is given access to the raw data under the data
provider's terms.

| Step | Script | Does |
|---|---|---|
| 1 | `s01_raw_to_saved_games.py` | load each match with [DataBallPy](https://github.com/Alek050/databallpy) 0.7.2; 1 Hz zero-lag 4th-order Butterworth filter on positions; speed and signed acceleration by central differences; playing position from the starting formation |
| 2 | `s02_extract_match_features.py` | per player and match: playing time, distance per speed zone, change of direction, acceleration/deceleration and sprint metrics, per-90 values |
| 3 | `s03_pseudonymise.py` | remove names, dates, match names and shirt numbers; replace player and club ids by the random codes (exact rebuild of `match_player_features.csv`) |

Details, thresholds and which matches were included: [`docs/tracking_pipeline.md`](docs/tracking_pipeline.md).
These steps need the optional dependencies (`pip install -e ".[tracking]"` or
`poetry install --all-extras`) and the private data paths in `config/paths.toml`
(copy `config/paths.example.toml`).

---

## 7. Software

Python 3.12.12 with pandas 2.3.3, numpy 2.3.5, scipy 1.18.1, statsmodels 0.15.0,
matplotlib 3.11.2 and python-docx 1.2.0 (all versions in `requirements.txt`);
DataBallPy 0.7.2 for steps 1 and 2. Rerunning gives identical files. Other
package versions will very likely give the same tables, but only the pinned
versions are guaranteed to.

## 8. Versions of this repository

Every change after submission (for example in response to reviewers) is
listed in [`CHANGELOG.md`](CHANGELOG.md), and each submitted version is tagged in
git (`git tag` lists them; `git checkout <tag>` gives that exact version).

## 9. License and citation

Code: MIT License (see `LICENSE`). Data: shared only to reproduce and check the
associated manuscript; please cite the manuscript when it is published.
