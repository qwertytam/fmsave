"""
Usage:
  fmsave.py FMUSERNAME GNUSERNAME CHROME_PATH SAVE_PATH (dlhtml | topd) [--max-html-pages=MAXPAGES] [--csvfn=CSVFN]
  fmsave.py -h | --help

Arguments:
  FMUSERNAME      Flight Memory usernane
  CHROME_PATH     Path to Chrome executable
  SAVE_PATH       Directory to save files to

Commands:
  dlhtml    Download html only; this or `topd` required
  topd      Convert html into a pandas dataframe; this or `dlhtml` required

Options:
  -h --help                     Show this screen
  --csvfn=CSVFN                 CSV file name for pandas save
  --max-html-pages=MAXPAGES     Maximum number of html pages to download and save

"""

import getpass
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
        
        fm_un = args['FMUSERNAME']
        gn_un = args['GNUSERNAME']
        chrome_path = args['CHROME_PATH']
        save_path = args['SAVE_PATH']
        
        dlhtml = args['dlhtml']
        topd = args['topd']
        # if topd:
        #         SAVE_CSV_FN = args['FN']
        
        max_pages = args['--max-html-pages']
        if max_pages is not None:
                max_pages = int(max_pages)
        
        csv_fn = args['--csvfn']
        if csv_fn is None:
                csv_fn = 'flights.csv'
        
        fd = FMDownloader(chrome_path=chrome_path, chrome_args=CHROME_OPTIONS)

        if dlhtml:
                # Download and save pages
                fm_pw = getpass.getpass(prompt="Flight Memory password:")
                fd.login(username=fm_un, password=fm_pw)
                fd.get_fm_pages(max_pages=max_pages)
                fd.save_fm_pages(save_path=save_path)

        if topd:
                # Read in already saved pages
                fd.read_fm_pages(save_path=save_path)
                fd.fm_pages_to_pandas()
                fd.add_lat_lon()
                fd.add_timezones(gnusername=gn_un)
                fd.save_pandas_to_csv(save_path=save_path, save_fn=csv_fn)
        # fd.read_pandas_from_csv(save_path=SAVE_PATH, save_fn=SAVE_CSV_FN)
        # fd.add_timezones(gnusername=GNUSERNAME, num_flights=10)
        # fd.save_pandas_to_csv(save_path=SAVE_PATH, save_fn=f"{SAVE_CSV_FN}")
