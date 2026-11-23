"""From raw optical tracking data to one row of physical-demand metrics per player per match.

Used by scripts/1_tracking_pipeline only. These steps need the raw tracking
data, which are not shared with this repository (see README, "Tracking
pipeline"). Needs the optional ``tracking`` dependencies (DataBallPy, pyarrow).

    positions.py                  detailed playing position from the starting formation
    kinematics.py                 filtered positions -> speed and signed acceleration
    change_of_direction.py        CoD counts (low / medium / high / total)
    acceleration_deceleration.py  acceleration and deceleration counts, distances, magnitudes
    sprint.py                     sprint counts, distances, durations, peak speed
    match_features.py             combines everything into one row per player per match
"""
