from pathlib import Path
import requests
import logging
import pandas as pd

mpath = Path(__file__).parent.absolute()

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
    
    fp = Path(fp).resolve()
    with open(fp, mode='wb') as f:
        f.write(response.content)
    
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
        fp = Path(OPENFLIGHTS_DATA_FP_BASE / fn).resolve()
        with open(fp, mode='wb') as f:
            f.write(response.content)
        logger.debug(f"Completed url:{url} file:{fp}")
    logger.info("Completed update")


def get_ourairport_data(airport_data_file=OURAIRPORTS_DATA_FILEPATH,
                     logger=module_logger):
    """
    Get airports data from module data set

    Args:
        airport_data_file: file path and name to csv file that contains
        required information. Typically using openflights information
        logger: logger to use
    """
    fp = Path(airport_data_file).resolve()
    return pd.read_csv(fp)