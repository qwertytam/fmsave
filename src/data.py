"""Providing data manipulation functionality"""

from __future__ import annotations

import logging
from pathlib import Path
import io
from typing import Any
from functools import lru_cache

import requests
from thefuzz import process  # type: ignore
import pandas as pd
import yaml
import wikipedia as wp  # type: ignore

import utils
from constants import URLs, FileExtensions, Timeouts

# Opt-in to future pandas behavior to avoid FutureWarning
pd.set_option("future.no_silent_downcasting", True)

mpath = Path(__file__).parent.absolute()
dpath = mpath.parent.absolute() / "data"

APP_NAME = "data"
_MODULE_LOGGER_NAME = f"{APP_NAME}.{__name__}"
module_logger = logging.getLogger(_MODULE_LOGGER_NAME)
module_logger.info("Module %s logger initialized", _MODULE_LOGGER_NAME)

OURAIRPORTS_DATA_FILEPATH = mpath.parent / "data/ourairports/airports.csv"

# add '.dat' to data set name
OPENFLIGHTS_DATA_URL_BASE = URLs.OPENFLIGHTS_DATA_BASE
OPENFLIGHTS_DATA_FP_BASE = mpath.parent / "data/openflights/"
OPENFLIGHTS_DATA_SETS = ["airports", "airlines", "planes"]
OPENFLIGHTS_FILE_EXT = FileExtensions.DAT

WIKI_DATA_FP_BASE = mpath.parent / "data/wiki/"


def get_yaml(
    fp: str,
    fn: str,
    logger: logging.Logger = module_logger,
) -> dict[str, Any]:
    """
    Read in yaml

    Args:
        fp: Path to yaml file relative to 'data' folder
        fn: File name read in. Function will append '.yaml' extension

    Returns:
        yaml
    """
    fn = fn + ".yaml"
    logger.debug("Getting yaml file: %s", dpath / fp / fn)
    with open(dpath / fp / fn, "rt", encoding="utf-8") as f:
        y = yaml.safe_load(f.read())
        f.close()
    return y


def _write_data(
    fp: Path | str, data: bytes, logger: logging.Logger = module_logger
) -> Path:
    fp = Path(fp).resolve()
    logger.debug("Writing data to: %s", fp)
    with open(fp, mode="wb") as f:
        f.write(data)

    return fp


def update_ourairport_data(
    url: str = URLs.OURAIRPORTS_DATA,
    fp: Path = OURAIRPORTS_DATA_FILEPATH,
    timeout: int = Timeouts.GEONAMES_DEFAULT,
    logger: logging.Logger = module_logger,
) -> None:
    """
    Update airports data set, typically using OurAirports data

    Args:
        url: URL to get data from
        fp: File path and name to save the data
        timeout: Timeout in seconds
        logger: logger to use
    """
    logger.debug("Updating airport data from %s", url)
    query_parameters = {"downloadformat": "csv"}
    response = requests.get(url, params=query_parameters, timeout=timeout)

    _ = _write_data(fp, response.content, logger)
    logger.info("Completed update or airport data from '%s'", url)


def update_openflights_data(
    timeout: int = Timeouts.GEONAMES_DEFAULT,
    logger: logging.Logger = module_logger,
) -> None:
    """
    Update openflights data set

    Args:
        timeout: Timeout in seconds
        logger: logger to use
    """
    logger.debug("Updating openflights data")
    query_parameters = {"downloadformat": "csv"}

    for data_set in OPENFLIGHTS_DATA_SETS:
        url = OPENFLIGHTS_DATA_URL_BASE + data_set + OPENFLIGHTS_FILE_EXT
        response = requests.get(url, params=query_parameters, timeout=timeout)

        fn = data_set + OPENFLIGHTS_FILE_EXT
        fp = _write_data(OPENFLIGHTS_DATA_FP_BASE / fn, response.content, logger)
        logger.debug("Completed url:%s file: %s", url, fp)
    logger.info("Completed update")


def _dl_wikipedia_table(
    page: str,
    table_no: int,
    logger: logging.Logger = module_logger,
) -> pd.DataFrame:
    logger.debug("Downloading wiki table number %s from %s", table_no, page)
    html = wp.page(page).html()  # .encode("UTF-8")
    sio = io.StringIO(html)
    df = pd.read_html(sio)[table_no]
    return df


def dl_aircraft_codes(logger: logging.Logger = module_logger) -> None:
    """
    Download ICAO and IATA codes from wikipedia

    Args:
        logger: Python logger to use
    """
    fn = "aircraft.csv"
    fp = Path(WIKI_DATA_FP_BASE).resolve()
    page = "List_of_aircraft_type_designators"
    table_no = 0

    df = _dl_wikipedia_table(page, table_no, logger)

    icao_col = df.filter(regex=r"(?i)icao").columns.to_list()[0]
    iata_col = df.filter(regex=r"(?i)iata").columns.to_list()[0]
    model_col = df.filter(regex=r"(?i)model").columns.to_list()[0]

    df = df.rename(
        columns={
            icao_col: "icao_type",
            iata_col: "iata_type",
            model_col: "model_name",
        }
    )

    df.to_csv(fp / fn, index=False, encoding="utf-8")
    logger.info("Completed download of aircraft codes")


def _get_data(
    filepath: Path,
    header: int | None = 0,  # pylint: disable=unused-argument
    index_col: int | bool | None = None,  # pylint: disable=unused-argument
    na_values: list[str] | None = None,  # pylint: disable=unused-argument
    **kwargs: Any,
) -> pd.DataFrame:
    filepath = Path(filepath).resolve()
    return pd.read_csv(filepath, **kwargs)


@lru_cache(maxsize=8)
def get_openflights_data(
    data_set: str = OPENFLIGHTS_DATA_SETS[0],
    header: int | None = None,
    supplemental: bool = False,
) -> pd.DataFrame:
    """
    Get open flights data from module data set

    Args:
        data_set: which data set to get e.g., airports, airlines, planes

    Returns:
        openflights data set as pandas data frame
    """
    supp = "_supplemental" if supplemental else ""
    fn = data_set + supp + OPENFLIGHTS_FILE_EXT
    fp = OPENFLIGHTS_DATA_FP_BASE / fn
    return _get_data(fp, header=header, index_col=False, na_values=["\\N", "-"])


@lru_cache(maxsize=1)
def get_ourairport_data(
    airport_data_file: Path = OURAIRPORTS_DATA_FILEPATH,
) -> pd.DataFrame:
    """
    Get airports data from module data set

    Args:
        airport_data_file: file path and name to csv file that contains
        required information. Typically using openflights information

    Returns:
        ourairport data set as pandas data frame
    """
    return _get_data(airport_data_file)


def select_fuzzy_match(
    df: pd.DataFrame,
    find_str: str,
    find_col: str,
    display_cols: list[str],
    col_widths: list[int],
    limit: int = 10,
    logger: logging.Logger = module_logger,
) -> pd.DataFrame | None:
    """
    Find and select fuzzy match

    Uses fuzzy logic to find the closest matches, then asks user which match to
    use

    Args:
        df: Data frame to find and select match from
        find_str: String to find closest match in df
        find_col: Which column in the data frame to find the match
        display_cols: Which columns to display when asking the user to select a match
        limit: How many closest matches to find and display
        logger: Logger to use

    Return:
        Row in df the user selected; 'None' if the user selects none
    """
    logger.debug("Finding string '%s' in column '%s'", find_str, find_col)
    res = process.extract(find_str, df[find_col], limit=limit)
    res = pd.DataFrame([(x[0], x[1]) for x in res], columns=["match", "score"])
    res = pd.merge(res, df[display_cols], left_on="match", right_on=find_col)

    print(f"\nChoose match for '{find_str}':")
    utils.print_selection_table(res, display_cols, col_widths)
    sel = input("Which number or 'N' for none: ")
    logger.debug(f"User entered '{sel}'")

    if sel.lower() == "n":
        logger.debug("Keeping current data\n")
        sel_row = None
    else:
        sel_row = df[df[find_col] == res.loc[int(sel) - 1, "match"]]
        logger.debug("Chosen\n%s\n", sel_row)

    return sel_row


def fuzzy_merge(
    df_l: pd.DataFrame,
    df_r: pd.DataFrame,
    key_l: str,
    key_r: str,
    threshold: int = 95,
    limit: int = 10,
) -> pd.DataFrame:
    """
    Merge two data frames based on fuzzy logic matching

    Uses fuzzy logic from the 'thefuzz' package to merge two data frames.
    Merge closeness is based on the Levenshtein distance.

    Args:
        df_l: Left data frame to join
        df_r: Right data frame to join
        key_l: Key column in the left data frame; column must be all strings
        key_r: Key column in the right data frame; column must be all strings
        threshold: How close the matches should be to return a match; higher is
        a closer match
        limit: The number of matches that will get returned, which are then
        sorted in descending order

    Returns:
        The merged data frames with all matches above the threshold in the
        'matches' column seperated by "', '"
    """
    sequences = df_r[key_r].tolist()

    matches = df_l[key_l].apply(lambda x: process.extract(x, sequences, limit=limit))
    df_l.loc[:, "matches"] = matches

    matches_2 = df_l["matches"].apply(
        lambda x: ", ".join(i[0] for i in x if i[1] >= threshold)
    )
    df_l.loc[:, "matches"] = matches_2

    return df_l


@lru_cache(maxsize=4)
def get_wiki_data(data_set: str = "aircraft", header: int = 0) -> pd.DataFrame:
    """
    Get open flights data from wiki

    Args:
        data_set: which data set to get e.g., aircraft

    Returns:
        wiki data set as pandas data frame
    """
    fn = data_set + ".csv"
    fp = WIKI_DATA_FP_BASE / fn
    df = _get_data(fp, header=header, index_col=False, na_values=["—"])

    fn = data_set + "_supplemental" + ".csv"
    fp = WIKI_DATA_FP_BASE / fn
    supp = _get_data(fp, header=header, index_col=False, na_values=["—"])

    df = pd.concat([df, supp], ignore_index=True)
    df = df.drop_duplicates()

    return df


def clear_data_caches() -> None:
    """Clear all cached data. Call this after updating reference data files."""
    get_ourairport_data.cache_clear()
    get_openflights_data.cache_clear()
    get_wiki_data.cache_clear()
