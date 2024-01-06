import io
import sys
from bs4 import BeautifulSoup as bs
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
import math
import pandas as pd
from pathlib import Path
import requests
from geonames import GeoNames
from geonames import (GeoNamesDateReturnError, GeoNamesStopError)
from geonames import EMPTY_TZ_DICT
from datetime import datetime as dt

import logging

APP_NAME = 'fmsave'
_module_logger_name = f'{APP_NAME}.{__name__}'
module_logger = logging.getLogger(_module_logger_name)
module_logger.info(f"Module {_module_logger_name} logger initialized")

AIRPORT_DATA_FILEPATH = '../data/airports.csv'

# FM_SEAT_POSN = ['Window', 'Aisle', 'Middle']
# FM_TRAVEL_CLASS = ['Economy', 'EconomyPlus', 'Business', 'First']
# FM_FLIGHT_AS = ['Passenger', 'Crew', 'Cockpit']
# FM_FLIGHT_REASON = ['Personal', 'Business', 'Virtual']

DEFAULT_LEGS = {
    'dep': {'date': 'dep_date_str', 'lat': 'lat_dep', 'lon': 'lon_dep'},
    'arr': {'date': 'arr_date_str', 'lat': 'lat_arr', 'lon': 'lon_arr'}
    }


def get_airport_data(
    url='https://davidmegginson.github.io/ourairports-data/airports.csv',
    fp=AIRPORT_DATA_FILEPATH):
    """
    Get ourairports data

    Args:
        url: URL to get data from
        fp: File path and name to save the data

    """
    query_parameters = {'downloadformat': 'csv'}
    response = requests.get(url, params=query_parameters)
    
    fp = Path(fp).resolve()
    with open(fp, mode='wb') as f:
        f.write(response.content)


def _get_str_for_pd(page):
    sio = io.StringIO(page)
    soup = bs(sio, 'html5lib')
    flight_tbl = soup.select_one('.container').find_all('table', recursive=False)[1]
    sub_tbls = flight_tbl.find_all('table', recursive=True)

    for sub_tbl in sub_tbls:
        fixed_text = '||'.join([txt for txt in sub_tbl.stripped_strings])
        sub_tbl.replace_with(fixed_text)
    
    return flight_tbl


def _check_create_path(dir_path):
    fp = Path(dir_path).resolve()
    print(f"Checking and creating path for {fp}")
    Path(fp).mkdir(parents=True, exist_ok=True)

class FMDownloader:

    def __init__(
            self,
            chrome_path,
            chrome_args,
    ):
        """
        Args:
            chrome_path: Path to Chrome browser executable
            chrome_args: Options to execute Chrome browser with
        """
        _class_name = 'FMDownloader'
        _class_logger_name = f'{_module_logger_name}.{_class_name}'
        self.logger = logging.getLogger(_class_logger_name)
        self.logger.debug(f"Class {_class_logger_name} initialized")
        
        # Set options to use Chromium with Selenium
        self.options = webdriver.ChromeOptions()
        self.options.binary_location = chrome_path
        for arg in chrome_args:
            self.options.add_argument(arg)
        self.driver = webdriver.Chrome(options=self.options)
        
        # Structures to hold web page data
        self.pages = []
        self.df = pd.DataFrame()


    def login(self,
              username,
              password,
              login_page='https://www.flightmemory.com/',
              timeout=5):
        """
        Log into Flight Memory website
        
        Args:
            username: Username
            password: Password
            login_page: Login page URL
            timeout: Time out in seconds
        """
        self.logger.info("Start login")
        self.driver.get(login_page)

        wait = WebDriverWait(self.driver, timeout)
        wait.until(EC.element_to_be_clickable(
            (By.NAME, "username"))).send_keys(username)
        self.logger.debug("Entered Username")

        wait.until(EC.element_to_be_clickable(
            (By.NAME, "passwort"))).send_keys(password)
        self.logger.debug("Entered Password")

        wait.until(EC.element_to_be_clickable(
            (By.XPATH, ".//input[@value='SignIn' and @type='submit']"))).click()
        self.logger.info("Entered login credentials")

        try:
            wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//*[contains(text(), 'FLIGHTDATA')]"))).click()
            self.logger.info("Found `FLIGHTDATA`; assumed login successful")
        except TimeoutException:
            self.logger.error("TimeoutException: Assuming wrong credentials; exiting")
            sys.exit()


    def _get_outer_html(self):
        WDSCRIPT_OUTER_HTML = 'return document.documentElement.outerHTML'
        self.pages.append(self.driver.execute_script(WDSCRIPT_OUTER_HTML))


    def _get_next_page(self, last_page_timeout=10):
        WebDriverWait(
            self.driver,
            last_page_timeout
            ).until(
                EC.element_to_be_clickable((
                        By.XPATH,
                        "//img[contains(@src,'/images/next.gif')]"
                        ))
                ).click()


    def get_fm_pages(self, max_pages=None, last_page_timeout=5):
        """
        Get html pages from Flight Memory website
        
        Args:
            max_pages: Maximum number of pages to get
            last_page_timeout: How long to wait for the 'next.gif' load; if 
            timeout exceeded, then assumed we are at the last page
        """
        self.logger.info("Starting data download")

        loop_counter = 0
        pages_len = len(self.pages)

        def _max_loops(loop_num):
            if max_pages is None:
                return True
            elif loop_num < max_pages:
                return True
            else:
                return False

        while _max_loops(loop_counter):
            loop_counter += 1
            self.logger.info(f"Entering loop {loop_counter}")
            self._get_outer_html()

            try:
                self._get_next_page(last_page_timeout)
                self.logger.debug(f"Found page for next loop at counter {loop_counter}")

            except TimeoutException:
                self.logger.info("TimeoutException; assuming at last page. "
                                  f"Ending at loop {loop_counter}")
                break
        
        if not _max_loops(loop_counter):
            self.logger.info(f"Exited loop as hit max for loop counter {loop_counter}")

        found_pages = len(self.pages) - pages_len
        pages_len = len(self.pages)
        self.logger.info(f"Found {found_pages} pages; pages now {pages_len} long")


    def save_fm_pages(self, save_path, prefix='flightmemory', fext='html'):
        """
        Save html pages
        
        Args:
            save_path: Path to save html files
            prefix: Flight name prefix; preppended to page number
            fext: File extension to use
        """
        _check_create_path(save_path)

        for page_num, page in enumerate(self.pages):
            fn = f'{prefix}{page_num+1}.{fext}'
            fp = Path(save_path, fn)
            self.logger.debug(f"Saving page number {page_num + 1} as {fp}")
            with open(fp, 'w') as f:
                f.write(page)

        self.logger.info(f"Saved {page_num + 1} pages")

    def read_fm_pages(self, save_path, fext='html'):
        """
        Read in Flight Memory html pages from disk
        
        Appends pages to existing self.pages data structure
        
        Args:
            save_path: Path to saved html files
            fext: File extension to filter on
        """
        self.logger.debug(f"Scanning path: {save_path} for {fext}")
        page_files = list(Path(save_path).glob(f'*.{fext}'))
        self.logger.info(f"Found {len(page_files)} pages")
        
        for page_num, page_file in enumerate(page_files):
            self.logger.debug(f"Reading page {page_num+1}: {page_file}")
            
            with open(page_file, 'r') as f:
                self.pages.append(f.read())
        
        self.logger.info(f"self.pages now length {len(self.pages)}")


    def _split_date_col(self):
        self.logger.debug(f"_split_date_col()")

        # Column has the following formats
        # Year only: YYYY or in regex r'^\d{4}'
        # Date only: DD-MM-YYYY or r'^\d{2}\.\d{2}\.\d{4}$'
        # Date with time: DD-MM-YYYY HH:MM or r'^\d{2}\.\d{2}\.\d{4}\s+\d{2}\:\d{2}$'
        # Date, time with day offset: DD-MM-YYYY HH:MM +/-D or r'^\d{2}\.\d{2}\.\d{4}\s+\d{2}\:\d{2}\s+\d{2}\:\d{2}\s+(?:\+|\-)\d)$'
        # Date with day offset: DD-MM-YYYY +/-D or r'^\d{2}\.\d{2}\.\d{4}\s+(?:\+|\-)\d)$'
        # Note there may be multiple spaces due to the collapsing of new lines
        
        # For the date with day offset case, need to ensure there are three
        # spaces for when we split into four columns
        pat = r'^(\d{2}\.\d{2}\.\d{4})\s+((?:\+|\-)\d)'
        repl = r'\1   \2'
        self.df['date_dept_arr_offset'] = self.df['date_dept_arr_offset']\
            .str.replace(pat=pat, repl=repl, regex=True)
        
        self.df[
            ['date',
             'dep_time',
             'arr_time',
             'date_offset']] = self.df['date_dept_arr_offset']\
                 .str.split(' ', expand=True)

        cols = [
            'date_dept_arr_offset',
            'date',
            'dep_time',
            'arr_time',
            'date_offset']
        self.df[cols] = self.df[cols].fillna(value='')
        
        pat = r'^\s*$'
        repl = '0'
        self.df['date_offset'] = self.df['date_offset']\
            .str.replace(pat=pat, repl=repl, regex=True)


    def _split_dist_col(self):
        self.logger.debug(f"_split_dist_col()")
        self.df[
            ['dist',
             'dist_units',
             'duration',
             'duration_units']] = self.df['dist_duration']\
                 .str.split('\\|\\|', expand=True)
        self.df['dist'] = pd.to_numeric(self.df['dist'].str.replace(',', ''))


    def _split_seat_col(self):
        self.logger.debug(f"_split_seat_col()")
        self.df[[
            'seat_class',
            'reason',
            'role',
            'reason']] = self.df['seat_class_place']\
                .str.split(' ', expand=True)
                 
        self.df[['seat', 'class']] = self.df['seat_class']\
            .str.split('\\/', expand=True)


    def _split_airplane_col(self):
        self.logger.debug(f"_split_airplane_col()")
        pat = '(?>\\s|^)('  # start of string 
        pat += '(?>N\\w{3,5})'  # for USA registrations
        pat += '|(?>[2BCDFGIPUZ]-\\w{3,4})'  # for registrations with single letter prefix
        pat += '|(?>\\w{2}-\\w{3,4})'  # all other country registrations
        pat += ')(?>\\s|$)'  # end of string
        self.df[
            ['airplane',
             'reg',
             'name']] = self.df['airplane_reg_name']\
                 .str.split(pat, expand=True)


    def _split_airline_col(self):
        self.logger.debug(f"_split_airline_col()")
        self.df[
            ['airline',
             'flightnum']] = self.df['airline_flightnum']\
                 .str.rsplit(' ', n=1, expand=True)


    def _dates_to_dt(self):
        self.logger.info(f"_dates_to_dt()")
        
        time_cols = ['dep_time', 'arr_time']
        for col in time_cols:
            time_is_empty =  self.df[col] == ''
            self.df.loc[~time_is_empty, col] = self.df.loc[~time_is_empty,'date'] +\
            ' ' + self.df.loc[~time_is_empty, col]
            self.df[col] = pd.to_datetime(self.df[col],
                                          format='mixed',
                                          dayfirst=True)
        
        self.df['date_offset'] = pd.to_timedelta(
            pd.to_numeric(self.df['date_offset']), unit='days')
        self.df['arr_time'] = self.df['arr_time'] \
            + self.df['date_offset']


    def _duration_to_td(self):
        self.logger.debug(f"_duration_to_td()")
        dur_hr_min = self.df['duration']\
            .str.split(':', expand=True).astype(int)
        self.df['duration'] = pd.to_timedelta(dur_hr_min[0], unit='h') + \
            pd.to_timedelta(dur_hr_min[1], unit='m')


    def fm_pages_to_pandas(self):
        """
        Convert Flight Memory web pages to pandas data frame
        """
        self.logger.debug(f"fm_pages_to_pandas()")
        for idx, page in enumerate(self.pages):
            self.logger.debug(f"Reading page {idx+1} to self.df")
            flight_tbl = _get_str_for_pd(page)
            df = pd.read_html(
                    io.StringIO(str(flight_tbl)), flavor='bs4')[0]
            self.df = pd.concat([self.df, df],
                                        ignore_index=True)
                
        self.logger.info(f"Finished reading {idx+1} pages to self.df")

        self.df.drop(columns=['Options'], inplace=True)
        self.df.rename(
            columns={
                self.df.columns[0]: 'flight_index',
                self.df.columns[1]: 'date_dept_arr_offset',
                self.df.columns[2]: 'dep_iata',
                self.df.columns[3]: 'dep_city_county_name',
                self.df.columns[4]: 'arr_iata',
                self.df.columns[5]: 'arr_city_county_name',
                self.df.columns[6]: 'dist_duration',
                self.df.columns[7]: 'airline_flightnum',
                self.df.columns[8]: 'airplane_reg_name',
                self.df.columns[9]: 'seat_class_place'
                },
            inplace=True,
            errors='raise',
            )

        self._split_date_col()
        self._split_dist_col()
        self._split_seat_col()
        self._split_airplane_col()
        self._split_airline_col()
        self._dates_to_dt()
        self._duration_to_td()

        self.df.drop(['date_dept_arr_offset',
                      'dist_duration',
                      'seat_class_place',
                      'seat_class',
                      'airplane_reg_name',
                      'airline_flightnum',
                      'date',
                      'date_offset',
                      'duration_units'],
                axis=1,
                inplace=True)

    def add_lat_lon(self, airport_data_file=AIRPORT_DATA_FILEPATH):
        """
        Add airport latitude and longitude information to pandas data frame
        
        Args:
            airport_data_file: file path and name to csv file that contains
            required information. Typically using openflights information
        """
        fp = Path(airport_data_file).resolve()
        airports = pd.read_csv(fp)

        airports = airports[
            ['ident',
             'name',
             'latitude_deg',
             'longitude_deg',
             'iso_country',
             'municipality',
             'iata_code']]
        
        airports = airports.rename(columns={
            'latitude_deg': 'lat',
            'longitude_deg': 'lon',
        })
        
        self.logger.debug(f"\n{airports.dtypes}")

        self.df = self.df.join(
            airports.set_index('iata_code'),
            how='left',
            on='dep_iata',
            lsuffix='_org',
            rsuffix='_dep')

        self.df = self.df.join(
            airports.set_index('iata_code'),
            how='left',
            on='arr_iata',
            lsuffix='_dep',
            rsuffix='_arr')
        
        self.logger.debug(f"Have added airport lat and lon data now have {self.df.dtypes}")


    def _add_tz(self, row, gnusername, legs=DEFAULT_LEGS):
        gn = GeoNames(username=gnusername)
            
        for leg in legs:
            tzid_col = f"{leg}_tzid"
            gmtoffset_col = f"{leg}_gmtoffset"
            
            self.logger.info(f"find_tz for {leg}: {row[legs[leg]['lat']]} {row[legs[leg]['lon']]} {row[legs[leg]['date']]}")
            
            try:
                tz = gn.find_tz(row[legs[leg]['lat']],
                                row[legs[leg]['lon']],
                                row[legs[leg]['date']],
                                timeout=3,
                                maxretries=5)
            except GeoNamesDateReturnError:
                tz = EMPTY_TZ_DICT
                self.logger.info(f"Using EMPTY_TZ_DICT, tz now:\n{tz}\n")
                for key in EMPTY_TZ_DICT:
                    if key in row:
                        tz[key] = row[key]
            row[tzid_col] = tz['tz_id']
            row[gmtoffset_col] = tz['gmt_offset']

        return row


    def add_timezones(self, gnusername, update_blanks_only=True, num_flights=None):
        """
        Add airport time zone information (IANA name and GMT offset) to pandas
        data frame
        
        Args:
            gnusername: GeoNames username
            update_blanks_only: Only update rows with no time zone information
            num_flights: Maximum number of flights (rows) to update
        """
        self.logger.info(f"add_timezones()")
        updated_flights = 0
        
        self.df['dep_date_str'] = self.df['dep_time'].dt.strftime('%Y-%m-%d')
        self.df['arr_date_str'] = self.df['arr_time'].dt.strftime('%Y-%m-%d')
        
        tz_cols = ['dep_tzid',
                   'dep_gmtoffset',
                   'arr_tzid',
                   'arr_gmtoffset']
        new_cols = list(set(tz_cols).difference(self.df.columns))
        if not new_cols:
            self.logger.info(f"No new_cols to add")
        else:
            self.logger.info(f"Adding new_cols: {new_cols}")
            for new_col in new_cols:
                self.df[new_col] = ''

        if num_flights is None:
            num_flights = len(self.df.index) + 1
        for index, row in self.df.iterrows():
            if updated_flights >= num_flights:
                break

            if type(row[tz_cols[0]]) is str:
                blank_row_test = row[tz_cols[0]] == ''
            else:
                blank_row_test = math.isnan(row[tz_cols[0]])

            if update_blanks_only and blank_row_test:
                try:
                    self.logger.info(f"Updating index {index} {row}")
                    row = self._add_tz(row, gnusername=gnusername)
                    for tz_col in tz_cols:
                        self.df.loc[index, tz_col] = row[tz_col]

                except GeoNamesStopError as err:
                    self.logger.error(f"stopping due to:\n{err}")
                
                updated_flights += 1
                self.logger.info(f"Updated index {index}"
                                 f"; have now updated {updated_flights} flights")
            else:
                self.logger.info(f"Skipping index {index}")
                next



    def save_pandas_to_csv(self, save_path, save_fn='flights.csv'):
        """
        Save pandas data frame to csv
        
        Args:
            save_path: Directory to save file to
            save_fn: File name to save file as
        """
        _check_create_path(save_path)
        fp = Path(save_path, save_fn)
        self.logger.info(f"Saving self.df to {fp}")
        self.df.to_csv(fp, index=False)
    
    def read_pandas_from_csv(self, save_path, save_fn='flights.csv'):
        """
        Read in csv to pandas data frame
        
        Args:
            save_path: Directory to find file in
            save_fn: File name read in
        """
        fp = Path(save_path, save_fn)
        self.logger.info(f"Reading self.df from {fp}")
        datetime_cols = [
            'dep_time',
            'arr_time',
            'dep_date_str',
            'arr_date_str',
        ]
        timedelata_cols = [
            'duration'
        ]
        col_types = {
            # 'flight_index': str,
            # 'dep_iata': str,
            # 'dep_city_county_name': str,
            # 'arr_iata': str,
            # 'arr_city_county_name': str,
            # 'dep_time': dt,
            # 'arr_time': dt,
            'dist': int,
            # 'dist_units': str,
            # 'duration': td,
            # 'reason': str,
            # 'role': str,
            # 'seat': str,
            # 'class': str,
            # 'airplane': str,
            # 'reg': str,
            # 'name_org': str,
            # 'airline': str,
            # 'flightnum': str,
            # 'ident_dep': str,
            # 'name_dep': str,
            'lat_dep': float,
            'lon_dep': float,
            # 'iso_country_dep': str,
            # 'municipality_dep': str,
            # 'ident_arr': str,
            # 'name': str,
            'lat_arr': float,
            'lon_arr': float,
            # 'iso_country_arr': str,
            # 'municipality_arr': str,
            # 'dep_date_str': dt,
            # 'arr_date_str': dt,
            'dep_tzid': str,
            'dep_gmtoffset': float,
            'arr_tzid': str,
            'arr_gmtoffset': float,
        }
        self.df = pd.read_csv(fp, dtype=col_types)
        
        for col in datetime_cols:
            self.df[col] = pd.to_datetime(
                self.df[col], format='ISO8601', yearfirst=True)

        for col in timedelata_cols:
            self.df[col] = pd.to_timedelta(
                self.df[col])

        self.logger.debug(f"Have read in csv; df types:\n{self.df.dtypes}")