"""
Usage:
  fmsave.py dlhtml <fm_un> <chrome_path> <save_path> [--max-pages=max_pages]
  fmsave.py tocsv <gn_un> <read_path> <fsave>
  fmsave.py upcsv <gn_un> <read_path> <fread> <fsave>
  fmsave.py uptz  <gn_un> <fread> <fsave>
  fmsave.py upair [<airurl>]
  fmsave.py -h | --help

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
  fread         Path to and file name of csv file to read from
  fsave         Path to and file name of csv file to save to
  gn_un         Geonames username
  read_path     Directory to read html files from
  save_path     Directory to save html files to
  

Options:
  -h --help                     Show this screen
  --max-html-pages=max_pages     Maximum number of html pages to download and save

"""
import sys
import getpass
from fmdownload import FMDownloader, get_airport_data, _check_create_path

from docopt import docopt

# Set up logging
import logging
import logging.config
import yaml
import pathlib

mpath = pathlib.Path(__file__).parent.absolute()

with open(mpath / 'logging.yaml','rt') as f:
    config=yaml.safe_load(f.read())
    f.close()
logging.config.dictConfig(config)

APP_NAME = 'fmsave'
logger = logging.getLogger(APP_NAME)

CHROME_OPTIONS = [
    '--headless',
    'start-maximized',
    '--disable-blink-features',
    '--disable-blink-features=AutomationControlled',
    ]

def dl_html(fd, fm_un, max_pages, save_path):
    # Download and save pages
    fm_pw = getpass.getpass(prompt="Flight Memory password:")
    fd.login(username=fm_un, password=fm_pw)
    fd.get_fm_pages(max_pages=max_pages)
    fd.save_fm_pages(save_path=save_path)

def html_to_csv(fd, gn_un, read_path, fsave):
    # Read in already saved pages
    fd.read_fm_pages(read_path=read_path)
    fd.fm_pages_to_pandas()
    fd.add_lat_lon()
    fd.add_timezones(gnusername=gn_un)
    fd.save_pandas_to_csv(save_fp=fsave)

def update_csv(fd, fdd, read_path, fread, fsave):
    fd.read_fm_pages(read_path=read_path)
    fd.fm_pages_to_pandas()
    fd.add_lat_lon()
    
    fdd.read_pandas_from_csv(read_fp=fread)
    fdd.find_updated_rows(fd)
    fd.save_pandas_to_csv(save_fp=fsave)

def update_tz():
    fd.read_pandas_from_csv(read_fp=fread)
    fd.add_timezones(gnusername=gn_un)
    fd.save_pandas_to_csv(save_fp=fsave)


if __name__ == '__main__':

    args = docopt(__doc__)

    airurl = args['airurl']
    chrome_path = args['chrome_path']    
    fm_un = args['fm_un']
    fread = args['fread']
    fsave = args['fsave']
    gn_un = args['gn_un']
    read_path = args['read_path']
    save_path = args['save_path']
    
    dlhtml = args['dlhtml']
    tocsv = args['tocsv']
    upair = args['upair']
    upcsv = args['upcsv']
    uptz = args['uptz']
    
    max_pages = args['--max-html-pages']
    if max_pages is not None:
        max_pages = int(max_pages)
    
    csv_fn = args['--csvfn']
    if csv_fn is None:
        csv_fn = 'flights.csv'
    
    fd = FMDownloader(chrome_path=chrome_path, chrome_args=CHROME_OPTIONS)

    if dlhtml:
        dl_html(fd, fm_un, max_pages, save_path)

    if tocsv:
        html_to_csv(fd, gn_un, read_path, fsave)

    if upair:
        get_airport_data(url=airurl)

    if upcsv:
        fdd = FMDownloader(chrome_path=chrome_path, chrome_args=CHROME_OPTIONS)
        update_csv(fd, fdd, read_path, fread, fsave)

    if uptz:
        update_tz(fd, gn_un, fread, fsave)
