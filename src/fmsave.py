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
  fmsave.py -h | --help

Options:
  -h --help  Show this screen
  -b DDMMYYYY --before=DDMMYYYY Remove existing data for flights on or before this date
  -a DDMMYYYY --after=DDMMYYYY Remove existing data for flights on or after this date
  -m MAX_PAGES --max-pages=MAX_PAGES  Maximum number of html pages to download and save

Commands:
  dlhtml    Download html pages
  tocsv     Convert html pages into a csv file
  upcsv     Update existing csv file based on downloaded html pages
  uptz      Update timezone information in existing csv file
  validate  Validate distances and times are correct
  upair     Update airport info data file; typically using https://davidmegginson.github.io/ourairports-data/airports.csv
  upof      Update openflights data files
  upwiki    Update wikipedia data, namely IATA and ICAO aircraft type codes
  export    Export data to given format


Arguments:
  airurl        URL to download airport info from
  chrome_path   Path to Chrome executable
  exp_format    Format to export to; one of ['openflights', 'myflightpath']
  fm_un         Flight Memory username
  fread         Path to and file name of csv file to read from
  fsave         Path to and file name of csv file to save to; if not provided, then uses <fread>
  gn_un         Geonames username
  read_path     Directory to read file(s) from
  save_path     Directory to save file(s) to
"""

import logging
import logging.config
from pathlib import Path
from docopt import docopt
import yaml

import logins
from data import update_ourairport_data, update_openflights_data, dl_aircraft_codes
from fmdownload import FMDownloader
import defaults
import utils

# Set up logging

mpath = Path(__file__).parent.absolute()

with open(mpath / "logging.yaml", "rt", encoding="utf8") as f:
    config = yaml.safe_load(f.read())
    f.close()
logging.config.dictConfig(config)

APP_NAME = "fmsave"
logger = logging.getLogger(APP_NAME)


def dl_html(fmdownloader, max_pages_dl, file_save_path):
    """
    Download html pages from flightmemory.com

    Args:
        fmdownloader: FMDownloader class object
        max_pages_dl: Maximum pages to download
        file_save_path: Directory to save html pages to
    """
    fmdownloader.fm_pw = logins.get_fm_pw()
    fmdownloader.login()
    fmdownloader.get_fm_pages(max_pages=max_pages_dl)
    fmdownloader.save_fm_pages(save_path=file_save_path)


def export_to(fmdownloader, export_format, file_read, file_save):
    """
    Export fmsave csv to other website format

    Args:
        fmdownloader: FMDownloader class object
        export_format: Format to export data to
        file_read: fmsave csv to read
        file_save: csv to save exported data to
    """
    fmdownloader.read_pandas_from_csv(read_fp=file_read)
    fmdownloader.export_to(export_format, file_save)


def html_to_csv(fmdownloader, geonames_un, file_read_path, file_save):
    """
    Convert flightmemory.com html pages to csv

    Args:
        fmdownloader: FMDownloader class object
        geonames_un: Geonames user name
        file_read_path: Path to read html files from
        file_save: csv to save exported data to
    """
    fmdownloader.read_fm_pages(read_path=file_read_path)
    fmdownloader.fm_pages_to_pandas()
    fmdownloader.add_lat_lon()
    fmdownloader.add_timezones(gnusername=geonames_un)
    fmdownloader.save_pandas_to_csv(save_fp=file_save)


def update_csv(
    fdu, fde, geonames_un, file_read_path, file_read, file_save, date_bf, date_af
):
    """
    Update fmsave csv file

    Args:
        fdu: FMDownloader class object to update data from
        fde: FMDownloader class object to update data to
        geonames_un: Geonames user name
        file_read_path: Path to read updated html files from
        file_read: fmsave csv to read old data from
        file_save: fmsave csv to save updated data to
        date_bf: Update data before this date
        date_af: Update data after this date
    """
    # Get updated data html
    fdu.read_fm_pages(read_path=file_read_path)
    fdu.fm_pages_to_pandas(date_bf, date_af)
    # utils.index_diagnostics(fdu.df['flight_index'], "fmsave fdu 1", logger=logger)

    fdu.add_lat_lon(date_bf, date_af)
    # utils.index_diagnostics(fdu.df['flight_index'], "fmsave fdu 2", logger=logger)

    # Get existing data from csv
    fde.read_pandas_from_csv(read_fp=file_read)
    # utils.index_diagnostics(fde.df['flight_index'], "fmsave fde 1", logger=logger)

    # Delete unwanted rows
    fde.remove_rows_by_date(date_bf, date_af)

    # Insert new flights
    fde.insert_updated_rows(fdu)
    fde.add_timezones(gnusername=geonames_un)

    #  Save to csv
    fde.save_pandas_to_csv(save_fp=file_save)


def update_tz(fmdownloader, geonames_un, file_read, file_save):
    """
    Update missing timezone data

    Args:
        fmdownloader: FMDownloader class object
        geonames_un: Geonames user name
        file_read: fmsave csv to read
        file_save: csv to save updated data to
    """
    fmdownloader.read_pandas_from_csv(read_fp=file_read)
    fmdownloader.add_timezones(gnusername=geonames_un)
    fmdownloader.save_pandas_to_csv(save_fp=file_save)


def validate_dist_times(fmdownloader, file_read, file_save):
    """
    Validate distance and times

    Args:
        fmdownloader: FMDownloader class object
        file_read: fmsave csv to read
        file_save: csv to save validated data to
    """
    fmdownloader.read_pandas_from_csv(read_fp=file_read)
    fmdownloader.validate_distance_times()
    fmdownloader.save_pandas_to_csv(save_fp=file_save)


def update_fm_data(fmdownloader, file_read):
    """
    Updating user flightmemory.com data

    Args:
        fmdownloader: FMDownloader class object
        file_read: fmsave csv to read
    """
    fmdownloader.read_pandas_from_csv(read_fp=file_read)
    fmdownloader.update_fm_data()


def update_wiki():
    """
    Updated wikipedia data, namely IATA and ICAO aircraft type codes
    """
    dl_aircraft_codes(logger)


if __name__ == "__main__":
    args = docopt(__doc__)

    dlhtml = args["dlhtml"]
    export = args["export"]
    tocsv = args["tocsv"]
    upair = args["upair"]
    upcsv = args["upcsv"]
    upof = args["upof"]
    uptz = args["uptz"]
    validate = args["validate"]
    upwiki = args["upwiki"]

    fread = args["<fread>"]
    fsave = args["<fsave>"]

    gn_un = args["<gn_un>"]
    read_path = args["<read_path>"]

    CHROME_PATH = args["<chrome_path>"]
    if CHROME_PATH is None:
        CHROME_PATH = defaults.DEFAULT_CHROME_PATH

    fd = FMDownloader(chrome_path=CHROME_PATH, chrome_args=defaults.CHROME_OPTIONS)

    if dlhtml:
        fd.fm_un = args["<fm_un>"]
        save_path = args["<save_path>"]
        max_pages = args["--max-pages"]
        if max_pages is not None:
            max_pages = int(max_pages)

        dl_html(fd, max_pages, save_path)

    if export:
        exp_format = args["<exp_format>"]
        export_to(fd, exp_format, fread, fsave)

    if tocsv:
        if fsave is None:
            fsave = fread
        html_to_csv(fd, gn_un, read_path, fsave)

    if upair:
        airurl = args["<airurl>"]
        if airurl is None:
            update_ourairport_data(logger=logger)
        else:
            update_ourairport_data(url=airurl, logger=logger)

    if upcsv:
        if fsave is None:
            fsave = fread

        dbf = args["--before"]
        daf = args["--after"]

        dbf = None if dbf is None else utils.date_to_dt(dbf)
        daf = None if daf is None else utils.date_to_dt(daf)

        fdd = FMDownloader(chrome_path=CHROME_PATH, chrome_args=defaults.CHROME_OPTIONS)
        update_csv(fd, fdd, gn_un, read_path, fread, fsave, dbf, daf)

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

    if upwiki:
        update_wiki()
