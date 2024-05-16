"""Holding dictionary based lookup conversions from flightmemory.com to other formats"""

from enum import Enum
from datetime import datetime as dt
from datetime import timedelta as td

# For converting strings to types
STR_TYPE_LU = {
    "str": str,
    "float": float,
    "int": int,
    "dt": dt,
    "td": td,
}


class DateTimeInfo(Enum):
    """Holds date time information available for each flight"""

    DT_INFO_YMDT = "YMDT"  # Year Month Day Time
    DT_INFO_YMDO = "YMDO"  # Year Month Day Offset
    DT_INFO_YMD = "YMD"  # Year Month Day
    DT_INFO_YM = "YM"  # Year Month
    DT_INFO_Y = "Y"  # Year


# For converting datetime representations to strings
DT_FMTS = {
    DateTimeInfo.DT_INFO_YMDT.value: {
        "fmt": "%Y-%m-%d %H:%M",
        "myflightpath_fmt": "%Y-%m-%d",
        "srccol": "time_dep",
    },
    DateTimeInfo.DT_INFO_YMDO.value: {
        "fmt": "%Y-%m-%d",
        "myflightpath_fmt": "%Y-%m-%d",
        "srccol": "date_as_dt",
    },
    DateTimeInfo.DT_INFO_YMD.value: {
        "fmt": "%Y-%m-%d",
        "myflightpath_fmt": "%Y-%m-%d",
        "srccol": "date_as_dt",
    },
    DateTimeInfo.DT_INFO_YM.value: {
        "fmt": "%Y-%m",
        "myflightpath_fmt": "%Y-%m-%d",
        "srccol": "date_as_dt",
    },
    DateTimeInfo.DT_INFO_Y.value: {
        "fmt": "%Y",
        "myflightpath_fmt": "%Y-%m-%d",
        "srccol": "date_as_dt",
    },
}


# FlightMemory options
FM_SEAT_POSITIONS = ["Window", "Aisle", "Middle"]
FM_CLASS = ["Economy", "EconomyPlus", "Business", "First"]
FM_ROLE = ["Passenger", "Crew", "Cockpit"]
FM_REASON = ["Personal", "Business", "virtuell"]


# For exporting flights
# OpenFlights
CLASS_OPENFLIGHTS_LU = {
    "First": "F",
    "Business": "C",
    "EconomyPlus": "P",
    "Economy": "Y",
}

SEAT_OPENFLIGHTS_LU = {
    "Window": "W",
    "Middle": "M",
    "Aisle": "A",
}

REASON_OPENFLIGHTS_LU = {
    "Business": "B",
    "Personal": "L",
    "Crew": "C",
    "Other": "O",
}

# MyFlightPath
CLASS_MYFLIGHTPATH_LU = {
    "Economy": "Y",
    "EconomyPlus": "W",
    "Business": "J",
    "First": "F",
    "Premium First": "R",
    "Private": "X",
}

REASON_MYFLIGHTPATH_LU = {
    "Business": "business",
    "Personal": "leisure",
    "Crew": "crew",
    "Other": "",
}
