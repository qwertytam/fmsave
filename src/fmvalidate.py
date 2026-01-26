"""Module providing time and distance validation functionality"""

from __future__ import annotations

from geopy import distance as dist
import pandas as pd


def calc_distance(
    df: pd.DataFrame,
    lat_fr: str,
    lon_fr: str,
    lat_to: str,
    lon_to: str,
) -> pd.Series:
    """
    Calculate distance between two points

    Uses the more accurate geodesic distance using geopy distance.distance

    Args:
        df: panda data frame containing the latitudes and longitudes
        lat_fr: name of column that contains the latitudes from; float
        lon_fr: name of column that contains the longitudes from; float
        lat_to: name of column that contains the latitudes to; float
        lon_to: name of column that contains the longitudes to; float

    Return:
        Panda series of distance in km
    """

    d_km = df.apply(
        lambda x: dist.distance((x[lat_fr], x[lon_fr]), (x[lat_to], x[lon_to])).km,
        axis=1,
    )

    return d_km


def calc_duration(
    df: pd.DataFrame,
    time_fr: str,
    time_to: str,
    gmtoffset_fr: str,
    gmtoffset_to: str,
) -> pd.Series:
    """
    Calculate time difference between two times in different time zones

    Args:
        df: panda data frame containing the relevant columns
        time_fr: name of column that contains the time from; float
        time_to: name of column that contains the time to; float
        gmtoffset_fr: name of column that contains the gmt offset from; float
        gmtoffset_to: name of column that contains the gmt offset to; float

    Return:
        Panda series of duration in timedelta
    """
    tz_fr = pd.to_timedelta(df[gmtoffset_fr], unit="hour")
    tz_to = pd.to_timedelta(df[gmtoffset_to], unit="hour")
    duration = df[time_to] - df[time_fr] + tz_fr - tz_to
    return duration
