# Data dictionary

All files are in `data/shared/`, comma-separated, one header row.

## `match_player_features.csv` (input of the analysis)

One row per player per match (8,584 rows). Made by `s03_pseudonymise.py`.

### Identifiers and match information

| Column | Meaning |
|---|---|
| `MD` | matchday (round) of the season, 1 to 34 |
| `team_side` | `home` or `away` in that match |
| `team_id` | club code, `T01` to `T18` (random) |
| `player_id` | player code, `P001` to `P515` (random) |
| `shirt_num` | shirt number in that match |
| `starter` | `True` if the player started the match |
| `position_specific` | detailed position from the starting formation (e.g. `Right Center Back`); `unknown` for substitutes |
| `column_id` | the player's column in the tracking data (`home_<shirt>` / `away_<shirt>`) |
| `playing_duration` | minutes with tracking data in the two halves, capped at 105 |

### Metrics

For every count and distance there is also a `<column>_per_90` version
(value / `playing_duration` × 90). Magnitudes, peaks and per-effort means have no
per-90 version. Speeds in m/s, accelerations in m/s², distances in m.

| Column | Meaning | In the manuscript as |
|---|---|---|
| `total_distance` | distance at all speeds | TD |
| `walking_distance`, `jogging_distance`, `running_distance` | distance at 0 to 2, 2 to 4, 4 to 5.5 m/s | (not reported) |
| `high_speed_running_distance` | distance at 5.5 to 7.0 m/s | HSRD |
| `sprinting_distance` | distance at 7.0 m/s or more | SpD |
| `CoD_low`, `CoD_medium`, `CoD_high`, `CoD_total` | change-of-direction counts by intensity, and their sum | CoD-low, -med, -high, -total |
| `n_acc_3`, `n_dec_3` | acceleration / deceleration events (beyond ±3 m/s² for at least 3 frames) | Acc-count, Dec-count |
| `dist_acc_3_m`, `dist_dec_3_m` | distance covered during those events | Acc-dist, Dec-dist |
| `n_hi_acc_standing`, `_trotting`, `_jogging`, `_running`, `n_acc_SP` | high-intensity accelerations with speed-dependent thresholds, and their sum | (not reported) |
| `mean_acc_magnitude_ms2`, `mean_dec_magnitude_ms2` | mean over all acceleration (deceleration) events of the peak value reached in each event | Acc-avg, Dec-avg |
| `peak_acc_ms2`, `peak_dec_ms2` | largest acceleration and deceleration in the match | Acc-peak, Dec-peak |
| `n_sprints` | sprint efforts (above 7.0 m/s, exit below 6.67 m/s, at least 1 m above threshold) | Sp-count |
| `sprint_distance_m` | distance covered during sprint efforts | (not reported; SpD uses `sprinting_distance`) |
| `mean_sprint_dist_m`, `mean_sprint_duration_s` | mean distance and duration per sprint effort | Mean sprint dist, Mean sprint dur |
| `mean_peak_speed_ms`, `max_peak_speed_ms` | mean and highest peak speed over the sprint efforts | (not reported) |
| `peak_speed_ms` | highest speed in the match | Peak speed |

Exact definitions and thresholds: `docs/tracking_pipeline.md` and the
docstrings in `src/match_variability/tracking/`.

## `match_player_features_clean.csv`

The rows of `match_player_features.csv` with at least 60 min played, for the
165 players with at least 17 such matches. Same columns. Made by step 4.

## `player_season_summary.csv` and `player_season_summary_no_gk.csv`

One row per eligible player (165; 148 without goalkeepers). Made by step 4.

| Column | Meaning |
|---|---|
| `player_id`, `team_id`, `team_side`, `shirt_num`, `starter`, `column_id` | most frequent value over the player's eligible matches |
| `position_specific_primary` | most frequent detailed position |
| `position_group_primary` | position group played in most eligible matches: GK, CB, FB, CM, AM, WM, WF, CF or Other (substitute appearances count as Other) |
| `matches_played` | number of eligible matches |
| `playing_duration_mean`, `_std`, `_cv` | minutes per eligible match |
| `<metric>_mean`, `<metric>_std` | mean and SD over the eligible matches, for every `*_per_90` metric and every magnitude/peak metric |
| `<metric>_cv` | within-player coefficient of variation in percent: 100 × SD / mean |

The analysis (step 5) uses the 146 players of `player_season_summary.csv` whose
`position_group_primary` is CM, CB, FB, AM or CF.
