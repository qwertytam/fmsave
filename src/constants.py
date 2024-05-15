"""Module for holding package constants."""

from enum import Enum


# Time and physical constants
class TimeConversions(Enum):
    """Holding time constants"""

    MINS_PER_HOUR = 60


class DistanceConversions(Enum):
    """Holding distance constants"""

    KM_TO_MILES = 1 / 1.6094
