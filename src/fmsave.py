"""
Usage:
  fmsave.py dlhtml <fm_un> <save_path> [<chrome_path> --max-pages=MAX_PAGES]
  fmsave.py tocsv <gn_un> <read_path> <fsave>
  fmsave.py upcsv <gn_un> <read_path> <fread> [<fsave> --before=DD-MM-YYYY --after=DD-MM-YYYY]
  fmsave.py uptz  <gn_un> <fread> [<fsave>]
  fmsave.py validate <fread> [<fsave>]
  fmsave.py upair [<airurl>]
  fmsave.py -h | --help

Options:
  -h --help  Show this screen
  -b DDMMYYYY --before=DDMMYYYY Remove existing data for flights on or before this date
  -a DDMMYYYY --after=DDMMYYYY Remove existing data for flights on or after this date
  -m MAX_PAGES --max-pages=MAX_PAGES  Maximum number of html pages to download and save

Commands:
  dlhtml    Download html pages
  tocsv     Convert html pages into a csv file
  upair     Update airport info data file
  upcsv     Update existing csv file based on downloaded html pages
  uptz      Update timezone information in existing csv file

Arguments:
  airurl        URL to download airport info from
  chrome_path   Path to Chrome executable
  fm_un         Flight Memory username
  fread         Path to and file name of csv file to read from; overwritten is fsave not provided
  fsave         Path to and file name of csv file to save to
  gn_un         Geonames username
  read_path     Directory to read html files from
  save_path     Directory to save html files to
"""

import logins
from data import update_ourairport_data
from fmdownload import FMDownloader
from datetime import datetime as dt
from docopt import docopt

from constants import DEFAULT_CHROME_PATH, CHROME_OPTIONS

# Set up logging
import logging
import logging.config
import yaml
from pathlib import Path

mpath = Path(__file__).parent.absolute()

with open(mpath / 'logging.yaml','rt') as f:
    config=yaml.safe_load(f.read())
    f.close()
logging.config.dictConfig(config)

APP_NAME = 'fmsave'
logger = logging.getLogger(APP_NAME)


def dl_html(fd, max_pages, save_path):
    fd.fm_pw = logins.get_fm_pw()
    fd.login()
    fd.get_fm_pages(max_pages=max_pages)
    fd.save_fm_pages(save_path=save_path)


def html_to_csv(fd, gn_un, read_path, fsave):
    fd.read_fm_pages(read_path=read_path)
    fd.fm_pages_to_pandas()
    fd.add_lat_lon()
    fd.add_timezones(gnusername=gn_un)
    fd.save_pandas_to_csv(save_fp=fsave)


def update_csv(fdu, fde, read_path, fread, fsave, dbf, daf):
    # Get updated data html
    fdu.read_fm_pages(read_path=read_path)
    fdu.fm_pages_to_pandas()
    fdu.add_lat_lon()
    
    # Get existing data from csv
    fde.read_pandas_from_csv(read_fp=fread)
    
    # Delete unwanted rows
    fde.remove_rows(dbf, daf)
    
    # Insert new flights
    fde.insert_updated_rows(fdu)
    fde.add_timezones(gnusername=gn_un)
    
    #  Save to csv
    fde.save_pandas_to_csv(save_fp=fsave)


def update_tz(fd, gn_un, fread, fsave):
    fd.read_pandas_from_csv(read_fp=fread)
    fd.add_timezones(gnusername=gn_un)
    fd.save_pandas_to_csv(save_fp=fsave)


def validate_dist_times(fd, fread, fsave):
    fd.read_pandas_from_csv(read_fp=fread)
    fd.validate_distance_times()
    fd.save_pandas_to_csv(save_fp=fsave)


def date_to_dt(ddmmyyyy):
    if ddmmyyyy:
        ddmmyyyy = dt.strptime(ddmmyyyy, "%d-%m-%Y")

    return ddmmyyyy

if __name__ == '__main__':
    args = docopt(__doc__)

    dlhtml = args['dlhtml']
    tocsv = args['tocsv']
    upair = args['upair']
    upcsv = args['upcsv']
    uptz = args['uptz']
    validate = args['validate']
    
    fread = args['<fread>']
    fsave = args['<fsave>']
    if fsave is None:
        fsave = fread

    gn_un = args['<gn_un>']
    read_path = args['<read_path>']

    chrome_path = args['<chrome_path>']
    if chrome_path is None:
        chrome_path = DEFAULT_CHROME_PATH

    fd = FMDownloader(chrome_path=chrome_path, chrome_args=CHROME_OPTIONS)

    if dlhtml:
        fd.fm_un = args['<fm_un>']
        save_path = args['<save_path>']
        max_pages = args['--max-pages']
        if max_pages is not None:
            max_pages = int(max_pages)

        dl_html(fd, max_pages, save_path)

    if tocsv:
        html_to_csv(fd, gn_un, read_path, fsave)

    if upair:
        airurl = args['<airurl>']
        if airurl is None:
            update_ourairport_data(logger=logger)
        else:
            update_ourairport_data(url=airurl, logger=logger)

    if upcsv:
        dbf = args['--before']
        daf = args['--after']
        
        dbf = date_to_dt(dbf)
        daf = date_to_dt(daf)

        fdd = FMDownloader(chrome_path=chrome_path, chrome_args=CHROME_OPTIONS)
        update_csv(fd, fdd, read_path, fread, fsave, dbf, daf)

    if uptz:
        update_tz(fd, gn_un, fread, fsave)
    
    if validate:
        validate_dist_times(fd, fread, fsave)
