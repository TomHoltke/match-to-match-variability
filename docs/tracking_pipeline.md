# Tracking pipeline: from raw tracking data to the shared input (steps 1 to 3)

These steps need the raw tracking and event data, which are not shared (see
README, section 6). They are documented here so that every processing choice
can be checked, and so that the pipeline can be rerun by anyone given access to
the raw data.

```
raw tracking + event files (private)
   │  step 1  s01_raw_to_saved_games.py       src/match_variability/tracking/kinematics.py, positions.py
   ▼
one preprocessed saved game per match (private)
   │  step 2  s02_extract_match_features.py   src/match_variability/tracking/match_features.py (+ 3 metric modules)
   ▼
identified feature table, one row per player per match (private)
   │  step 3  s03_pseudonymise.py             src/match_variability/pseudonymise.py
   ▼
data/shared/match_player_features.csv (shared)  ->  steps 4 and 5 (README, section 4)
```

## Data

One full season of a European top-tier league: 18 clubs, 34 matchdays, 306
matches. Per match the data provider delivered four files with the same name
stem: TRACAB optical tracking (`<stem>.dat`, `<stem> metadata.xml`; 25 Hz,
4th generation) and Opta event data and line-ups (`<stem> f24.xml`,
`<stem> f7.xml`).

| | Matches |
|---|---|
| scheduled in the season | 306 |
| delivered with tracking data | 303 |
| could not be loaded without error by DataBallPy, excluded | 23 |
| **processed and in the shared data** | **280** |

The private file `match_list.csv` (in the private data folder) lists every
delivered match: its file stem, the name of its saved game (which carries the
matchday as `MDxx`), the matchday, and `included` (1 or 0). Steps 1 and 2 only
process matches with `included = 1`, so a rerun uses exactly the same 280 matches.

## Step 1: raw data -> saved games (`s01_raw_to_saved_games.py`)

Per match:

1. **Load** tracking and event data with DataBallPy 0.7.2 (`get_game`,
   provider `tracab` and `opta`).
2. **Player kinematics** (`tracking/kinematics.py`), per player:
   - zero-lag 4th-order Butterworth low-pass filter, 1 Hz cut-off, on x and y
     (gaps are bridged by linear interpolation for filtering only and set back
     to missing afterwards);
   - velocity by central differences (`numpy.gradient`) of the filtered
     positions, no further filter; speeds above 12 m/s are set to missing;
   - signed acceleration = d(speed)/dt by central differences, no further
     filter (positive = speeding up, negative = slowing down); values beyond
     ±10 m/s² are set to missing.
3. **Ball** (not used in the analysis): DataBallPy's Savitzky-Golay filters.
4. **Playing position** (`tracking/positions.py`): each starter's detailed
   position from the team's formation and the player's place in it (Opta f7).
   Substitutes get no position.
5. **Save** with DataBallPy (`save_game`), one folder per match.

## Step 2: saved games -> feature table (`s02_extract_match_features.py`)

Per match and player (`tracking/match_features.py`), using periods 1 and 2 only:

| Metric | Definition | Module |
|---|---|---|
| playing time | minutes with tracking data, capped at 105 | `match_features.py` |
| distance per speed zone | DataBallPy `get_covered_distance`: 0-2, 2-4, 4-5.5, 5.5-7 (HSRD), ≥ 7 m/s (sprint distance); total = all speeds | `match_features.py` |
| change of direction | deceleration phase (a < −2 m/s²) followed within 25 frames (1 s) by an acceleration phase (a > +2 m/s²), turn angle ≥ 20° between the two displacement vectors; low = entry speed < 3 m/s and angle 20-59°; medium = entry speed < 3 m/s and angle 60-119°, or entry speed 3-5.5 m/s and angle 20-119°; high = all other events; total = sum (Deutsch et al., 2025; Dos'Santos et al., 2018) | `change_of_direction.py` |
| acceleration / deceleration | events where signed acceleration exceeds +3 m/s² (below −3 m/s²) for at least 3 frames (0.12 s): count, distance covered during the events, mean over events of the peak value per event; match peak = largest value in the match (Harper et al., 2019) | `acceleration_deceleration.py` |
| sprints | effort starts above 7.0 m/s and ends below 6.67 m/s, at least 1 m covered above 7.0 m/s: count, mean distance and duration per effort; peak speed = highest speed in the match | `sprint.py` |

Counts and distances also get a per-90 value (value / playing time × 90).
All values are rounded to 2 decimals. Plausibility checks against literature
ranges are printed per match but do not remove any data.

## Step 3: pseudonymisation (`s03_pseudonymise.py`)

Removes `date`, `match` and `full_name`, and replaces the data provider's
player id and the club name by neutral codes (`P001` ..., `T01` ...). The codes
were assigned once at random and stored in two private key files; step 3
reuses them, so it rebuilds `data/shared/match_player_features.csv` exactly.
Without key files (new data), new random keys are made.

## Running steps 1 to 3

With access to the raw data:

```bash
pip install -e ".[tracking]"              # or: poetry install --all-extras
cp config/paths.example.toml config/paths.toml   # set the private data paths
python scripts/1_tracking_pipeline/s01_raw_to_saved_games.py   # slow: several hours for all matches
python scripts/1_tracking_pipeline/s02_extract_match_features.py
python scripts/1_tracking_pipeline/s03_pseudonymise.py
```

Steps 1 and 2 accept `--only "<saved game name>"` to try a single match first.
Existing saved games and an existing feature table are never overwritten unless
`--overwrite` is given.
