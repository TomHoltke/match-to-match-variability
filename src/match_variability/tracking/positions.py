"""Detailed playing position of each starter, from the team's starting formation.

The Opta line-up file (f7) gives each team's formation (e.g. "4231") and each
starter's ``formation_place`` (1 to 11). The tables below translate that pair
into a position label such as "Right Center Back". Substitutes get no
position (None, written as "unknown" in the feature table). A player's
position group in the analysis is the group played most often over
the eligible matches (see cleaning.py, ``_primary_position_group``).

Unchanged from the code that produced the shared data.
"""

from __future__ import annotations

from enum import Enum


class PositionType(Enum):
    Goalkeeper = "Goalkeeper"
    RightBack = "Right Back"
    LeftBack = "Left Back"
    RightCenterBack = "Right Center Back"
    LeftCenterBack = "Left Center Back"
    CenterBack = "Center Back"
    RightWingBack = "Right Wing Back"
    LeftWingBack = "Left Wing Back"
    RightDefensiveMidfield = "Right Defensive Midfield"
    CenterDefensiveMidfield = "Center Defensive Midfield"
    LeftDefensiveMidfield = "Left Defensive Midfield"
    RightMidfield = "Right Midfield"
    RightCentralMidfield = "Right Central Midfield"
    CenterMidfield = "Center Midfield"
    LeftCentralMidfield = "Left Central Midfield"
    LeftMidfield = "Left Midfield"
    RightAttackingMidfield = "Right Attacking Midfield"
    CenterAttackingMidfield = "Center Attacking Midfield"
    LeftAttackingMidfield = "Left Attacking Midfield"
    RightWing = "Right Wing"
    LeftWing = "Left Wing"
    Striker = "Striker"
    RightForward = "Right Forward"
    LeftForward = "Left Forward"
    Unknown = "Unknown"


class FormationType(Enum):
    FOUR_FOUR_TWO = "4-4-2"
    FOUR_ONE_TWO_ONE_TWO = "4-1-2-1-2"
    FOUR_THREE_THREE = "4-3-3"
    FOUR_FIVE_ONE = "4-5-1"
    FOUR_FOUR_ONE_ONE = "4-4-1-1"
    FOUR_ONE_FOUR_ONE = "4-1-4-1"
    FOUR_TWO_THREE_ONE = "4-2-3-1"
    FOUR_THREE_TWO_ONE = "4-3-2-1"
    FIVE_THREE_TWO = "5-3-2"
    FIVE_FOUR_ONE = "5-4-1"
    THREE_FIVE_TWO = "3-5-2"
    THREE_FOUR_THREE = "3-4-3"
    FOUR_TWO_TWO_TWO = "4-2-2-2"
    THREE_FIVE_ONE_ONE = "3-5-1-1"
    THREE_FOUR_TWO_ONE = "3-4-2-1"
    THREE_FOUR_ONE_TWO = "3-4-1-2"
    THREE_ONE_FOUR_TWO = "3-1-4-2"
    THREE_ONE_TWO_ONE_THREE = "3-1-2-1-3"
    FOUR_ONE_THREE_TWO = "4-1-3-2"
    FOUR_THREE_ONE_TWO = "4-3-1-2"
    THREE_TWO_FOUR_ONE = "3-2-4-1"
    THREE_THREE_THREE_ONE = "3-3-3-1"


formation_name_mapping = {
    "442": FormationType.FOUR_FOUR_TWO,
    "41212": FormationType.FOUR_ONE_TWO_ONE_TWO,
    "433": FormationType.FOUR_THREE_THREE,
    "451": FormationType.FOUR_FIVE_ONE,
    "4411": FormationType.FOUR_FOUR_ONE_ONE,
    "4141": FormationType.FOUR_ONE_FOUR_ONE,
    "4231": FormationType.FOUR_TWO_THREE_ONE,
    "4321": FormationType.FOUR_THREE_TWO_ONE,
    "532": FormationType.FIVE_THREE_TWO,
    "541": FormationType.FIVE_FOUR_ONE,
    "352": FormationType.THREE_FIVE_TWO,
    "343": FormationType.THREE_FOUR_THREE,
    "4222": FormationType.FOUR_TWO_TWO_TWO,
    "3511": FormationType.THREE_FIVE_ONE_ONE,
    "3421": FormationType.THREE_FOUR_TWO_ONE,
    "3412": FormationType.THREE_FOUR_ONE_TWO,
    "3142": FormationType.THREE_ONE_FOUR_TWO,
    "343d": FormationType.THREE_ONE_TWO_ONE_THREE,
    "4132": FormationType.FOUR_ONE_THREE_TWO,
    "4312": FormationType.FOUR_THREE_ONE_TWO,
    "3241": FormationType.THREE_TWO_FOUR_ONE,
    "3331": FormationType.THREE_THREE_THREE_ONE,
}

formation_position_mapping = {
    FormationType.FOUR_FOUR_TWO: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightBack,
        3: PositionType.LeftBack, 4: PositionType.RightCentralMidfield,
        5: PositionType.RightCenterBack, 6: PositionType.LeftCenterBack,
        7: PositionType.RightMidfield, 8: PositionType.LeftCentralMidfield,
        9: PositionType.LeftForward, 10: PositionType.RightForward,
        11: PositionType.LeftMidfield,
    },
    FormationType.FOUR_ONE_TWO_ONE_TWO: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightBack,
        3: PositionType.LeftBack, 4: PositionType.CenterDefensiveMidfield,
        5: PositionType.RightCenterBack, 6: PositionType.LeftCenterBack,
        7: PositionType.RightMidfield, 8: PositionType.CenterAttackingMidfield,
        9: PositionType.LeftForward, 10: PositionType.RightForward,
        11: PositionType.LeftMidfield,
    },
    FormationType.FOUR_THREE_THREE: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightBack,
        3: PositionType.LeftBack, 4: PositionType.CenterMidfield,
        5: PositionType.RightCenterBack, 6: PositionType.LeftCenterBack,
        7: PositionType.RightMidfield, 8: PositionType.LeftMidfield,
        9: PositionType.Striker, 10: PositionType.RightWing,
        11: PositionType.LeftWing,
    },
    FormationType.FOUR_FIVE_ONE: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightBack,
        3: PositionType.LeftBack, 4: PositionType.RightCentralMidfield,
        5: PositionType.RightCenterBack, 6: PositionType.LeftCenterBack,
        7: PositionType.RightMidfield, 8: PositionType.LeftCentralMidfield,
        9: PositionType.Striker, 10: PositionType.CenterMidfield,
        11: PositionType.LeftMidfield,
    },
    FormationType.FOUR_FOUR_ONE_ONE: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightBack,
        3: PositionType.LeftBack, 4: PositionType.RightCentralMidfield,
        5: PositionType.RightCenterBack, 6: PositionType.LeftCenterBack,
        7: PositionType.RightMidfield, 8: PositionType.LeftCentralMidfield,
        9: PositionType.Striker, 10: PositionType.CenterAttackingMidfield,
        11: PositionType.LeftMidfield,
    },
    FormationType.FOUR_ONE_FOUR_ONE: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightBack,
        3: PositionType.LeftBack, 4: PositionType.CenterDefensiveMidfield,
        5: PositionType.RightCenterBack, 6: PositionType.LeftCenterBack,
        7: PositionType.RightMidfield, 8: PositionType.RightCentralMidfield,
        9: PositionType.Striker, 10: PositionType.LeftCentralMidfield,
        11: PositionType.LeftMidfield,
    },
    FormationType.FOUR_TWO_THREE_ONE: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightBack,
        3: PositionType.LeftBack, 4: PositionType.RightCentralMidfield,
        5: PositionType.RightCenterBack, 6: PositionType.LeftCenterBack,
        7: PositionType.RightAttackingMidfield, 8: PositionType.LeftCentralMidfield,
        9: PositionType.Striker, 10: PositionType.CenterAttackingMidfield,
        11: PositionType.LeftAttackingMidfield,
    },
    FormationType.FOUR_THREE_TWO_ONE: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightBack,
        3: PositionType.LeftBack, 4: PositionType.CenterMidfield,
        5: PositionType.RightCenterBack, 6: PositionType.LeftCenterBack,
        7: PositionType.LeftMidfield, 8: PositionType.RightMidfield,
        9: PositionType.Striker, 10: PositionType.RightAttackingMidfield,
        11: PositionType.LeftAttackingMidfield,
    },
    FormationType.FIVE_THREE_TWO: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightBack,
        3: PositionType.LeftBack, 4: PositionType.LeftCenterBack,
        5: PositionType.CenterBack, 6: PositionType.RightCenterBack,
        7: PositionType.RightCentralMidfield, 8: PositionType.CenterMidfield,
        9: PositionType.LeftForward, 10: PositionType.RightForward,
        11: PositionType.LeftCentralMidfield,
    },
    FormationType.FIVE_FOUR_ONE: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightBack,
        3: PositionType.LeftBack, 4: PositionType.LeftCenterBack,
        5: PositionType.CenterBack, 6: PositionType.RightCenterBack,
        7: PositionType.RightMidfield, 8: PositionType.RightCentralMidfield,
        9: PositionType.Striker, 10: PositionType.LeftCentralMidfield,
        11: PositionType.LeftMidfield,
    },
    FormationType.THREE_FIVE_TWO: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightMidfield,
        3: PositionType.LeftMidfield, 4: PositionType.LeftCenterBack,
        5: PositionType.CenterBack, 6: PositionType.RightCenterBack,
        7: PositionType.RightCentralMidfield, 8: PositionType.LeftCentralMidfield,
        9: PositionType.LeftForward, 10: PositionType.RightForward,
        11: PositionType.CenterMidfield,
    },
    FormationType.THREE_FOUR_THREE: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightMidfield,
        3: PositionType.LeftMidfield, 4: PositionType.LeftCenterBack,
        5: PositionType.CenterBack, 6: PositionType.RightCenterBack,
        7: PositionType.RightCentralMidfield, 8: PositionType.LeftCentralMidfield,
        9: PositionType.Striker, 10: PositionType.RightWing,
        11: PositionType.LeftWing,
    },
    FormationType.FOUR_TWO_TWO_TWO: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightBack,
        3: PositionType.LeftBack, 4: PositionType.RightDefensiveMidfield,
        5: PositionType.RightCenterBack, 6: PositionType.LeftCenterBack,
        7: PositionType.RightCentralMidfield, 8: PositionType.LeftDefensiveMidfield,
        9: PositionType.LeftForward, 10: PositionType.RightForward,
        11: PositionType.LeftCentralMidfield,
    },
    FormationType.THREE_FIVE_ONE_ONE: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightMidfield,
        3: PositionType.LeftMidfield, 4: PositionType.LeftCenterBack,
        5: PositionType.CenterBack, 6: PositionType.RightCenterBack,
        7: PositionType.RightDefensiveMidfield, 8: PositionType.LeftDefensiveMidfield,
        9: PositionType.Striker, 10: PositionType.CenterAttackingMidfield,
        11: PositionType.CenterDefensiveMidfield,
    },
    FormationType.THREE_FOUR_TWO_ONE: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightMidfield,
        3: PositionType.LeftMidfield, 4: PositionType.LeftCenterBack,
        5: PositionType.CenterBack, 6: PositionType.RightCenterBack,
        7: PositionType.RightCentralMidfield, 8: PositionType.LeftCentralMidfield,
        9: PositionType.Striker, 10: PositionType.RightForward,
        11: PositionType.LeftForward,
    },
    FormationType.THREE_FOUR_ONE_TWO: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightMidfield,
        3: PositionType.LeftMidfield, 4: PositionType.LeftCenterBack,
        5: PositionType.CenterBack, 6: PositionType.RightCenterBack,
        7: PositionType.RightCentralMidfield, 8: PositionType.LeftCentralMidfield,
        9: PositionType.CenterAttackingMidfield, 10: PositionType.RightForward,
        11: PositionType.LeftForward,
    },
    FormationType.THREE_ONE_FOUR_TWO: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightMidfield,
        3: PositionType.LeftMidfield, 4: PositionType.CenterBack,
        5: PositionType.RightCenterBack, 6: PositionType.LeftCenterBack,
        7: PositionType.RightCentralMidfield, 8: PositionType.CenterDefensiveMidfield,
        9: PositionType.RightForward, 10: PositionType.LeftWing,
        11: PositionType.LeftCentralMidfield,
    },
    FormationType.THREE_ONE_TWO_ONE_THREE: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightMidfield,
        3: PositionType.LeftMidfield, 4: PositionType.LeftCenterBack,
        5: PositionType.CenterBack, 6: PositionType.RightCenterBack,
        7: PositionType.CenterAttackingMidfield, 8: PositionType.CenterDefensiveMidfield,
        9: PositionType.Striker, 10: PositionType.RightWing,
        11: PositionType.LeftWing,
    },
    FormationType.FOUR_ONE_THREE_TWO: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightBack,
        3: PositionType.LeftBack, 4: PositionType.CenterDefensiveMidfield,
        5: PositionType.RightCenterBack, 6: PositionType.LeftCenterBack,
        7: PositionType.RightWing, 8: PositionType.CenterAttackingMidfield,
        9: PositionType.RightForward, 10: PositionType.LeftForward,
        11: PositionType.LeftWing,
    },
    FormationType.FOUR_THREE_ONE_TWO: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightBack,
        3: PositionType.LeftBack, 4: PositionType.CenterMidfield,
        5: PositionType.RightCenterBack, 6: PositionType.LeftCenterBack,
        7: PositionType.RightMidfield, 8: PositionType.CenterAttackingMidfield,
        9: PositionType.RightForward, 10: PositionType.LeftForward,
        11: PositionType.LeftMidfield,
    },
    FormationType.THREE_TWO_FOUR_ONE: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightDefensiveMidfield,
        3: PositionType.LeftDefensiveMidfield, 4: PositionType.LeftCenterBack,
        5: PositionType.CenterBack, 6: PositionType.RightCenterBack,
        7: PositionType.RightCentralMidfield, 8: PositionType.LeftCentralMidfield,
        9: PositionType.Striker, 10: PositionType.RightWing,
        11: PositionType.LeftWing,
    },
    FormationType.THREE_THREE_THREE_ONE: {
        0: None, 1: PositionType.Goalkeeper, 2: PositionType.RightDefensiveMidfield,
        3: PositionType.LeftDefensiveMidfield, 4: PositionType.LeftCenterBack,
        5: PositionType.CenterBack, 6: PositionType.RightCenterBack,
        7: PositionType.CenterAttackingMidfield, 8: PositionType.CenterDefensiveMidfield,
        9: PositionType.Striker, 10: PositionType.RightWing,
        11: PositionType.LeftWing,
    },
}


def add_position_specific(game):
    """Add position_specific column with None handling."""
    for team_type in ["away", "home"]:
        formation_str = str(int(getattr(game, f"{team_type}_formation")))
        players_df = getattr(game, f"{team_type}_players")

        if formation_str in formation_name_mapping:
            formation_type = formation_name_mapping[formation_str]
            position_mapping = formation_position_mapping.get(formation_type, {})

            def get_position(row):
                if not row["starter"]:
                    return None
                position_type = position_mapping.get(row["formation_place"])
                if position_type is None:
                    return "Unknown"
                return position_type.value

            players_df["position_specific"] = players_df.apply(get_position, axis=1)
        else:
            players_df["position_specific"] = None
