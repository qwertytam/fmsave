from pathlib import Path
import requests
import logging
import pandas as pd

mpath = Path(__file__).parent.absolute()

APP_NAME = 'airport'
_module_logger_name = f'{APP_NAME}.{__name__}'
module_logger = logging.getLogger(_module_logger_name)
module_logger.info(f"Module {_module_logger_name} logger initialized")

AIRPORT_DATA_FILEPATH = mpath.parent / 'data/airports.csv'

def update_airport_data(
    url='https://davidmegginson.github.io/ourairports-data/airports.csv',
    fp=AIRPORT_DATA_FILEPATH,
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


def get_airport_data(airport_data_file=AIRPORT_DATA_FILEPATH,
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