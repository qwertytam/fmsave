from pathlib import Path
import requests
import logging
from thefuzz import process
import pandas as pd
import yaml

import utils

mpath = Path(__file__).parent.absolute()
dpath = mpath.parent.absolute() / 'data'

APP_NAME = 'data'
_module_logger_name = f'{APP_NAME}.{__name__}'
module_logger = logging.getLogger(_module_logger_name)
module_logger.info(f"Module {_module_logger_name} logger initialized")

OURAIRPORTS_DATA_FILEPATH = mpath.parent / 'data/ourairports/airports.csv'

# add '.dat' to data set name
OPENFLIGHTS_DATA_URL_BASE = 'https://raw.githubusercontent.com/jpatokal/openflights/master/data/'
OPENFLIGHTS_DATA_FP_BASE = mpath.parent / 'data/openflights/'
OPENFLIGHTS_DATA_SETS = ['airports', 'airlines', 'planes']
OPENFLIGHTS_FILE_EXT = '.dat'


def get_yaml(fp, fn, logger=module_logger):
    """
    Read in yaml
    
    Args:
        fp: Path to yaml file relative to 'data' folder
        fn: File name read in. Function will append '.yaml' extension
    """
    fn = fn + '.yaml'
    logger.info(f"Getting yaml file: {dpath / fp / fn}")
    with open(dpath / fp / fn,'rt') as f:
        y = yaml.safe_load(f.read())
        f.close()
    return y


def _write_data(fp, data, logger=module_logger):
    fp = Path(fp).resolve()
    with open(fp, mode='wb') as f:
        f.write(data)
    
    return fp


def update_ourairport_data(
    url='https://davidmegginson.github.io/ourairports-data/airports.csv',
    fp=OURAIRPORTS_DATA_FILEPATH,
    logger=module_logger):
    """
    Update airports data set, typically using OurAirports data

    Args:
        url: URL to get data from
        fp: File path and name to save the data
        logger: logger to use
    """
    logger.debug(f"Updating airport data from {url}")
    query_parameters = {'downloadformat': 'csv'}
    response = requests.get(url, params=query_parameters)
    
    _ = _write_data(fp, response.content, logger)
    logger.debug("Completed update")


def update_openflights_data(logger=module_logger):
    """
    Update openflights data set

    Args:
        logger: logger to use
    """
    logger.debug("Updating openflights data")
    query_parameters = {'downloadformat': 'csv'}
    
    for data_set in OPENFLIGHTS_DATA_SETS:
        url = OPENFLIGHTS_DATA_URL_BASE + data_set + OPENFLIGHTS_FILE_EXT
        response = requests.get(url, params=query_parameters)
        
        fn = data_set + OPENFLIGHTS_FILE_EXT
        fp = _write_data(OPENFLIGHTS_DATA_FP_BASE / fn, response.content, logger)
        logger.debug(f"Completed url:{url} file:{fp}")
    logger.info("Completed update")


def _get_data(
    filepath,
    header_row='infer',
    names=None,
    dtype=None,
    index_col=None,
    na_values=None,
    logger=module_logger):

    filepath = Path(filepath).resolve()
    
    return pd.read_csv(filepath,
                       header=header_row,
                       names=names,
                       dtype=dtype,
                       index_col=index_col,
                       na_values=na_values,
                       encoding='utf-8')


def get_openflights_data(
    data_set=OPENFLIGHTS_DATA_SETS[0],
    header_row=None,
    cnames=None,
    dtypes=None,
    logger=module_logger):
    """
    Get open flights data from module data set

    Args:
        data_set: which data set to get e.g., airports, airlines, planes
        logger: logger to use
    """
    fn = data_set + OPENFLIGHTS_FILE_EXT
    fp = OPENFLIGHTS_DATA_FP_BASE / fn
    return _get_data(fp,
                     header_row=header_row,
                     names=cnames,
                     dtype=dtypes,
                     index_col=False,
                     na_values="\\N",
                     logger=logger)


def get_ourairport_data(airport_data_file=OURAIRPORTS_DATA_FILEPATH,
                     logger=module_logger):
    """
    Get airports data from module data set

    Args:
        airport_data_file: file path and name to csv file that contains
        required information. Typically using openflights information
        logger: logger to use
    """
    return _get_data(airport_data_file, logger=logger)


def select_fuzzy_match(df, find_str, find_col, display_cols, col_widths, limit=10, logger=module_logger):
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
        Row in df the user selected; `None` if the user selects none
    """
    res = process.extract(find_str, df[find_col], limit=limit)
    res = pd.DataFrame([(x[0], x[1]) for x in res], columns=['match', 'score'])
    res = pd.merge(res, df[display_cols], left_on='match', right_on=find_col)

    logger.info(f"\nChoose match for '{find_str}':")
    utils.print_selection_table(res, display_cols, col_widths)
    sel = input("Which number or 'N' for none:")
    logger.debug(f"User entered `{sel}`")

    if sel.lower() == 'n':
        logger.debug("Keeping current data\n")
        sel_row = None
    else:
        sel_row = df[df[find_col] == res.loc[int(sel)-1, 'match']]
        logger.debug(f"Chosen\n{sel_row}\n")

    return sel_row