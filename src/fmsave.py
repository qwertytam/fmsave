"""
Usage:
  fmsave.py dlhtml <fm_un> <save_path> [<chrome_path> --max-pages=MAX_PAGES]
  fmsave.py tocsv <gn_un> <read_path> <fsave>
  fmsave.py upcsv <gn_un> <read_path> <fread> [<fsave> --before=DD-MM-YYYY --after=DD-MM-YYYY]
  fmsave.py uptz  <gn_un> <fread> [<fsave>]
  fmsave.py validate <fread> [<fsave>]
  fmsave.py upair [<airurl>]
  fmsave.py upof
  fmsave.py upwiki
  fmsave.py export <exp_format> <fread> [<fsave>]
  fmsave.py updatefm <fread>
  fmsave.py -h | --help

Options:
  -h --help  Show this screen
  -b DDMMYYYY --before=DDMMYYYY Remove existing data for flights on or before this date
  -a DDMMYYYY --after=DDMMYYYY Remove existing data for flights on or after this date
  -m MAX_PAGES --max-pages=MAX_PAGES  Maximum number of html pages to download and save

Commands:
  dlhtml    Download html pages
  export    Export data to given format
  tocsv     Convert html pages into a csv file
  upair     Update airport info data file
  upcsv     Update existing csv file based on downloaded html pages
  upof      Update openflights data files
  uptz      Update timezone information in existing csv file

Arguments:
  airurl        URL to download airport info from
  chrome_path   Path to Chrome executable
  exp_format    Format to export to; one of ['openflights', ]
  fm_un         Flight Memory username
  fread         Path to and file name of csv file to read from
  fsave         Path to and file name of csv file to save to; if not provided, then uses <fread>
  gn_un         Geonames username
  read_path     Directory to read file(s) from
  save_path     Directory to save file(s) to
"""

import logins
from data import update_ourairport_data, update_openflights_data, dl_aircraft_codes
from fmdownload import FMDownloader
from datetime import datetime as dt
from docopt import docopt
import utils
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


def export_to(fd, exp_format, fread, fsave):
    fd.read_pandas_from_csv(read_fp=fread)
    fd.export_to(exp_format, fsave)


def html_to_csv(fd, gn_un, read_path, fsave):
    fd.read_fm_pages(read_path=read_path)
    fd.fm_pages_to_pandas()
    fd.add_lat_lon()
    fd.add_timezones(gnusername=gn_un)
    fd.save_pandas_to_csv(save_fp=fsave)


def update_csv(fdu, fde, read_path, fread, fsave, dbf, daf):
    # Get updated data html
    fdu.read_fm_pages(read_path=read_path)
    fdu.fm_pages_to_pandas(dbf, daf)
    # utils.index_diagnostics(fdu.df['flight_index'], "fmsave fdu 1", logger=logger)

    fdu.add_lat_lon(dbf, daf)
    # utils.index_diagnostics(fdu.df['flight_index'], "fmsave fdu 2", logger=logger)
    
    # Get existing data from csv
    fde.read_pandas_from_csv(read_fp=fread)
    # utils.index_diagnostics(fde.df['flight_index'], "fmsave fde 1", logger=logger)
    
    # Delete unwanted rows
    fde.remove_rows_by_date(dbf, daf)
    utils.index_diagnostics(fde.df['flight_index'], "fmsave fde 2", logger=logger)
    
    # Insert new flights
    fde.insert_updated_rows(fdu)
    utils.index_diagnostics(fde.df['flight_index'], "fmsave fde 3", logger=logger)
    fde.add_timezones(gnusername=gn_un)
    utils.index_diagnostics(fde.df['flight_index'], "fmsave fde 4", logger=logger)
    
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


def update_fm_data(fd, fread):
    fd.read_pandas_from_csv(read_fp=fread)
    fd.update_fm_data()


def update_wiki():
    dl_aircraft_codes(logger)
    

def date_to_dt(ddmmyyyy):
    if ddmmyyyy:
        ddmmyyyy = dt.strptime(ddmmyyyy, "%d-%m-%Y")

    return ddmmyyyy


if __name__ == '__main__':
    args = docopt(__doc__)

    dlhtml = args['dlhtml']
    export = args['export']
    tocsv = args['tocsv']
    upair = args['upair']
    upcsv = args['upcsv']
    upof = args['upof']
    uptz = args['uptz']
    updatefm = args['updatefm']
    validate = args['validate']
    upwiki = args['upwiki']
    test = args['test']
    
    fread = args['<fread>']
    fsave = args['<fsave>']

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

    if export:
        exp_format = args['<exp_format>']
        if fsave is None:
            fsave = 'openflights.csv'
        export_to(fd, exp_format, fread, fsave)

    if tocsv:
        if fsave is None:
            fsave = fread
        html_to_csv(fd, gn_un, read_path, fsave)

    if upair:
        airurl = args['<airurl>']
        if airurl is None:
            update_ourairport_data(logger=logger)
        else:
            update_ourairport_data(url=airurl, logger=logger)

    if upcsv:
        if fsave is None:
            fsave = fread

        dbf = args['--before']
        daf = args['--after']
        
        dbf = date_to_dt(dbf)
        daf = date_to_dt(daf)

        fdd = FMDownloader(chrome_path=chrome_path, chrome_args=CHROME_OPTIONS)
        update_csv(fd, fdd, read_path, fread, fsave, dbf, daf)

    if upof:
        update_openflights_data(logger=logger)

    if uptz:
        if fsave is None:
            fsave = fread
        update_tz(fd, gn_un, fread, fsave)
    
    if validate:
        if fsave is None:
            fsave = fread
        validate_dist_times(fd, fread, fsave)
    
    if updatefm:
        update_fm_data(fd, fread)
    
    if upwiki:
        update_wiki()
