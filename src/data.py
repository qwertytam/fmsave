"""Providing data manipulation functionality"""

import logging
import re
from pathlib import Path
import io
import requests
from functools import lru_cache
from thefuzz import process
import pandas as pd
import yaml
import wikipedia as wp

import utils

mpath = Path(__file__).parent.absolute()
dpath = mpath.parent.absolute() / "data"

APP_NAME = "data"
_module_logger_name = f"{APP_NAME}.{__name__}"
module_logger = logging.getLogger(_module_logger_name)
module_logger.info("Module %s logger initialized", _module_logger_name)

OURAIRPORTS_DATA_FILEPATH = mpath.parent / "data/ourairports/airports.csv"

# add '.dat' to data set name
OPENFLIGHTS_DATA_URL_BASE = (
    "https://raw.githubusercontent.com/jpatokal/openflights/master/data/"
)
OPENFLIGHTS_DATA_FP_BASE = mpath.parent / "data/openflights/"
OPENFLIGHTS_DATA_SETS = ["airports", "airlines", "planes"]
OPENFLIGHTS_FILE_EXT = ".dat"

WIKI_DATA_FP_BASE = mpath.parent / "data/wiki/"


def get_yaml(fp, fn, logger=module_logger):
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


def _write_data(fp, data, logger=module_logger):
    fp = Path(fp).resolve()
    logger.debug("Writing data to: %s", fp)
    with open(fp, mode="wb") as f:
        f.write(data)

    return fp


def update_ourairport_data(
    url="https://davidmegginson.github.io/ourairports-data/airports.csv",
    fp=OURAIRPORTS_DATA_FILEPATH,
    timeout=10,
    logger=module_logger,
):
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


def update_openflights_data(timeout=10, logger=module_logger):
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


def _dl_wikipedia_table(page, table_no, logger=module_logger):
    logger.debug("Downloading wiki table number %s from %s", table_no, page)
    html = wp.page(page).html()  # .encode("UTF-8")
    sio = io.StringIO(html)
    df = pd.read_html(sio)[table_no]
    return df


def dl_aircraft_codes(logger=module_logger):
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

    icao_col = df.filter(regex=re.compile(r"icao", re.IGNORECASE)).columns.to_list()[0]
    iata_col = df.filter(regex=re.compile(r"iata", re.IGNORECASE)).columns.to_list()[0]
    model_col = df.filter(regex=re.compile(r"model", re.IGNORECASE)).columns.to_list()[
        0
    ]

    df = df.rename(
        columns={
            icao_col: "icao_type",
            iata_col: "iata_type",
            model_col: "model_name",
        }
    )

    df.to_csv(fp / fn, index=False, encoding="utf-8")
    logger.info("Completed download of aircraft codes")


def _get_data(filepath, **kwargs):
    filepath = Path(filepath).resolve()
    return pd.read_csv(filepath, **kwargs)


@lru_cache(maxsize=8)
def get_openflights_data(
    data_set=OPENFLIGHTS_DATA_SETS[0], header=None, supplemental=False
):
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
    return _get_data(
        fp, header=header, index_col=False, na_values=["\\N", "-"]
    )


@lru_cache(maxsize=1)
def get_ourairport_data(airport_data_file=OURAIRPORTS_DATA_FILEPATH):
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
    df, find_str, find_col, display_cols, col_widths, limit=10, logger=module_logger
):
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


def fuzzy_merge(df_l, df_r, key_l, key_r, threshold=95, limit=10):
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
    df_l["matches"] = matches

    matches_2 = df_l["matches"].apply(
        lambda x: ", ".join(i[0] for i in x if i[1] >= threshold)
    )
    df_l["matches"] = matches_2

    return df_l


@lru_cache(maxsize=4)
def get_wiki_data(data_set="aircraft", header=0):
    """
    Get open flights data from wiki

    Args:
        data_set: which data set to get e.g., aircraft

    Returns:
        wiki data set as pandas data frame
    """
    fn = data_set + ".csv"
    fp = WIKI_DATA_FP_BASE / fn
    df = _get_data(fp, header=header, index_col=False, na_values="—")

    fn = data_set + "_supplemental" + ".csv"
    fp = WIKI_DATA_FP_BASE / fn
    supp = _get_data(fp, header=header, index_col=False, na_values="—")

    df = pd.concat([df, supp], ignore_index=True)
    df = df.drop_duplicates()

    return df


def clear_data_caches():
    """Clear all cached data. Call this after updating reference data files."""
    get_ourairport_data.cache_clear()
    get_openflights_data.cache_clear()
    get_wiki_data.cache_clear()
