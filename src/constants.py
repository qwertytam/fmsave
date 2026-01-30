"""Constants used throughout fmsave."""

from enum import Enum, IntEnum


# Time and physical constants
class TimeConversions(Enum):
    """Holding time constants"""

    MINS_PER_HOUR = 60


class DistanceConversions(Enum):
    """Conversion values between different distance measurements"""

    KM_TO_MILES = 0.621371
    MILES_TO_KM = 1.60934


class Timeouts(IntEnum):
    """Timeout values in seconds."""

    LOGIN = 5
    PAGE_LOAD = 10
    LAST_PAGE = 5
    API_CALL = 3
    API_CALL_DEFAULT = 1
    GEONAMES_DEFAULT = 10


class APILimits(IntEnum):
    """API rate limits and retry settings."""

    GEONAMES_HOURLY = 1000
    MAX_RETRIES = 3
    GEONAMES_MAX_RETRIES = 5


class URLs:
    """External URLs used by the application."""

    FLIGHT_MEMORY_BASE = "https://www.flightmemory.com"
    FLIGHT_MEMORY_SIGNIN = f"{FLIGHT_MEMORY_BASE}/signin/"
    FLIGHT_MEMORY_LOGIN = f"{FLIGHT_MEMORY_BASE}/"
    GEONAMES_TIMEZONE = "https://secure.geonames.org/timezoneJSON"
    OURAIRPORTS_DATA = "https://davidmegginson.github.io/ourairports-data/airports.csv"
    OPENFLIGHTS_DATA_BASE = (
        "https://raw.githubusercontent.com/jpatokal/openflights/master/data/"
    )


class ChromeDefaults:
    """Default Chrome/Chromium settings."""

    DEFAULT_PATH = "/Applications/Chromium.app/Contents/MacOS/Chromium"


class FileExtensions:
    """File extensions used in the application."""

    HTML = "html"
    CSV = "csv"
    YAML = "yaml"
    DAT = ".dat"
