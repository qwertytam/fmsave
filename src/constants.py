from enum import Enum


# Time and physical constants
class TimeConversions(Enum):
    MINS_PER_HOUR = 60


class DistanceConversions(Enum):
    KM_TO_MILES = 1 / 1.6094
