"""
Usage:
  fmsave.py FMUSERNAME FMPASSWORD GNUSERNAME CHROME_PATH SAVE_PATH (dlhtml | topd) [--max-html-pages=MAXPAGES]
  fmsave.py -h | --help

Arguments:
  FMUSERNAME      Flight Memory usernane
  FMPASSWORD      Flight Memory password
  CHROME_PATH     Path to Chrome executable
  SAVE_PATH       Directory to save files to

Commands:
  dlhtml    Download html only; this or `topd` required
  topd      Convert html into a pandas dataframe; this or `dlhtml` required

Options:
  -h --help     Show this screen

"""

import os
from dotenv import load_dotenv
from fmdownload import FMDownloader

from docopt import docopt

# Set up logging
import logging
import logging.config
import yaml

with open('logging.yaml','rt') as f:
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

if __name__ == '__main__':
        args = docopt(__doc__)
        
        print(args)
        
        FMUSERNAME = args['FMUSERNAME']
        FMPASSWORD = args['FMPASSWORD']
        GNUSERNAME = args['GNUSERNAME']
        CHROME_PATH = args['CHROME_PATH']
        SAVE_PATH = args['SAVE_PATH']
        
        dlhtml = args['dlhtml']
        topd = args['topd']
        # if topd:
        #         SAVE_CSV_FN = args['FN']
        
        max_pages = args['--max-html-pages']
        if max_pages is not None:
                max_pages = int(max_pages)
        
        fd = FMDownloader(chrome_path=CHROME_PATH, chrome_args=CHROME_OPTIONS)

        # Download and save pages
        fd.login(username=FMUSERNAME, password=FMPASSWORD)
        fd.get_fm_pages(max_pages=max_pages)
        
        if dlhtml:
                fd.save_fm_pages(save_path=SAVE_PATH)

        # # Read in already saved pages
        # # fd.read_fm_pages(save_path=SAVE_PATH)
        # fd.fm_pages_to_pandas()
        # fd.add_lat_lon()
        # fd.add_timezones(gnusername=GNUSERNAME, num_flights=4)
        # fd.save_pandas_to_csv(save_path=SAVE_PATH, save_fn=SAVE_CSV_FN)
        # fd.read_pandas_from_csv(save_path=SAVE_PATH, save_fn=SAVE_CSV_FN)
        # fd.add_timezones(gnusername=GNUSERNAME, num_flights=10)
        # fd.save_pandas_to_csv(save_path=SAVE_PATH, save_fn=f"{SAVE_CSV_FN}")
