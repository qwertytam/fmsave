import io
import sys
from bs4 import BeautifulSoup as bs
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
import math
import re
import numpy as np
import pandas as pd
from pathlib import Path
from geonames import GeoNames
from geonames import (GeoNamesDateReturnError, GeoNamesStopError)
from geonames import EMPTY_TZ_DICT
from datetime import datetime as dt
import logging

import airport
import utils

mpath = Path(__file__).parent.absolute()

APP_NAME = 'fmsave'
_module_logger_name = f'{APP_NAME}.{__name__}'
module_logger = logging.getLogger(_module_logger_name)
module_logger.info(f"Module {_module_logger_name} logger initialized")

DEFAULT_LEGS = {
    'dep': {'date': 'dep_date_str', 'lat': 'lat_dep', 'lon': 'lon_dep'},
    'arr': {'date': 'arr_date_str', 'lat': 'lat_arr', 'lon': 'lon_arr'}
    }

DT_INFO_YMDT = "YMDT"
DT_INFO_YMD = "YMD"
DT_INFO_YM = "YM"
DT_INFO_Y = "Y"


def _get_str_for_pd(page):
    sio = io.StringIO(page)
    soup = bs(sio, 'html5lib')
    flight_tbl = soup.select_one('.container').find_all('table', recursive=False)[1]
    sub_tbls = flight_tbl.find_all('table', recursive=True)

    for sub_tbl in sub_tbls:
        fixed_text = '||'.join([txt for txt in sub_tbl.stripped_strings])
        sub_tbl.replace_with(fixed_text)
    
    return flight_tbl


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
            self.logger.debug(f"Exited loop as hit max for loop counter {loop_counter}")

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
        utils.check_create_path(save_path)

        for page_num, page in enumerate(self.pages):
            fn = f'{prefix}{page_num+1:04d}.{fext}'
            fp = Path(save_path, fn)
            self.logger.debug(f"Saving page number {page_num + 1} as {fp}")
            with open(fp, 'w') as f:
                f.write(page)

        self.logger.info(f"Saved {page_num + 1} pages")

    def read_fm_pages(self, read_path, fext='html'):
        """
        Read in Flight Memory html pages from disk

        Appends pages to existing self.pages data structure
        
        Args:
            read_path: Path to saved html files
            fext: File extension to filter on
        """
        self.logger.debug(f"Scanning path '{read_path}' for '*.{fext}'")
        page_files = list(Path(read_path).glob(f'*.{fext}'))
        
        if len(page_files) == 0:
            raise ValueError("No '*.{fext}' files found to read in")

        self.logger.info(f"Found {len(page_files)} '*.{fext}' files")
        
        for page_num, page_file in enumerate(page_files):
            self.logger.debug(f"Reading file {page_num+1}: {page_file}")
            
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
        
        expected_cols = 4
        str_split = self.df['date_dept_arr_offset'].str.split(' ',
                                                              expand=True,
                                                              n=expected_cols)
        
        if len(str_split.columns) == 1:
            self.logger.debug("only one column, adding one more")
            str_split[1] = pd.Series('', index=str_split.index)

        if len(str_split.columns) == 2:
            self.logger.debug("only two columns, adding one more")
            str_split[2] = pd.Series('', index=str_split.index)
        
        if len(str_split.columns) == 3:
            self.logger.debug("only three columns, adding one more")
            str_split[3] = pd.Series('', index=str_split.index)

        self.df[
            ['date',
             'dep_time',
             'arr_time',
             'date_offset']] = str_split

        self.df['dt_info'] = None

        # year, month, day and time available
        condition = ~self.df['dep_time'].isna()
        self.df.loc[condition, 'dt_info'] = DT_INFO_YMDT

        pat = r'(\d{2})-(\d{2})-(\d{4})'
        repl = r'\3-\2-\1'
        self.df.loc[condition, 'date'] = self.df.loc[condition, 'date']\
            .str.replace(pat=pat, repl=repl, regex=True) 

        # year, month, day only available
        pat = r'(\d{2})-(\d{2})-(\d{4})'
        condition = (self.df['dt_info'].isna()) & (self.df['date'].str.match(pat))
        self.df.loc[condition, 'dt_info'] = DT_INFO_YMD
        
        repl = r'\3-\2-\1'
        self.df.loc[condition, 'date'] = self.df.loc[condition, 'date']\
            .str.replace(pat=pat, repl=repl, regex=True)

        # year, month only available
        pat = r'(\d{2})-(\d{4})'
        condition = (self.df['dt_info'].isna()) & (self.df['date'].str.match(pat))
        self.df.loc[condition, 'dt_info'] = DT_INFO_YM
        
        repl = r'\2-\1'
        self.df.loc[condition, 'date'] = self.df.loc[condition, 'date']\
            .str.replace(pat=pat, repl=repl, regex=True)

        # year only available
        pat = r'\d{4}'
        condition = (self.df['dt_info'].isna()) & (self.df['date'].str.match(pat))
        self.df.loc[condition, 'dt_info'] = DT_INFO_Y
        
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
        
        expected_cols = 4
        str_split = self.df['seat_class_place'].str.split(' ',
                                                          expand=True,
                                                          n=expected_cols)
        
        if len(str_split.columns) == 1:
            self.logger.debug("only one column, adding one more")
            str_split[1] = pd.Series('', index=str_split.index)

        if len(str_split.columns) == 2:
            self.logger.debug("only two columns, adding one more")
            str_split[2] = pd.Series('', index=str_split.index)
        
        if len(str_split.columns) == 3:
            self.logger.debug("only three columns, adding one more")
            str_split[3] = pd.Series('', index=str_split.index)
        
        self.df[[
            'seat_class',
            'reason',
            'role',
            'reason']] = str_split
                 
        self.df[['seat', 'class']] = self.df['seat_class']\
            .str.split('\\/', expand=True)


    def _split_airplane_col(self):
        self.logger.debug(f"_split_airplane_col()")
        pat = '(?>\\s|^)('  # start of string 
        pat += '(?>N\\w{3,5})'  # for USA registrations
        pat += '|(?>[2BCDFGIPUZ]-\\w{3,4})'  # for registrations with single letter prefix
        pat += '|(?>\\w{2}-\\w{3,4})'  # all other country registrations
        pat += ')(?>\\s|$)'  # end of string

        expected_cols = 3
        str_split = self.df['airplane_reg_name']\
            .str.split(pat, expand=True, n=expected_cols)
        
        if len(str_split.columns) == 1:
            self.logger.debug("only one column, adding one more")
            str_split[1] = pd.Series('', index=str_split.index)

        if len(str_split.columns) == 2:
            self.logger.debug("only two columns, adding one more")
            str_split[2] = pd.Series('', index=str_split.index)

        self.df[
            ['airplane',
             'reg',
             'name']] = str_split


    def _split_airline_col(self):
        self.logger.debug(f"_split_airline_col()")

        expected_cols = 2
        str_split = self.df['airline_flightnum']\
            .str.rsplit(' ', n=1, expand=True)
        
        if len(str_split.columns) == 1:
            self.logger.debug("only one column, adding one more")
            str_split[1] = pd.Series('', index=str_split.index)

        self.df[
            ['airline',
             'flightnum']] = str_split


    def _dates_to_dt(self):
        self.logger.debug(f"_dates_to_dt()")
        
        time_cols = ['dep_time', 'arr_time']
        self.logger.debug(f"\n{self.df.loc[0, ['date', 'dep_time', 'arr_time', 'date_offset']]}")
        for col in time_cols:
            time_is_empty =  self.df[col].isna()

            self.df.loc[~time_is_empty, col] = self.df.loc[~time_is_empty, 'date'] +\
            ' ' + self.df.loc[~time_is_empty, col]

            self.df[col] = pd.to_datetime(self.df[col],
                                          format='mixed',
                                          dayfirst=True)

        self.df['date_as_dt'] = pd.to_datetime(self.df['date'],
                                          format='mixed',
                                          dayfirst=True)

        self.df['date_offset'] = self.df['date_offset'].fillna(0)
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
            
        self.logger.info(f"Finished reading {idx+1} pages to self.df; "
                         f"read in {len(self.df.index):,} flights")

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
                    #   'date',
                      'date_offset',
                      'duration_units'],
                axis=1,
                inplace=True)

        self.df = self.df.replace(r'^\s*$', np.nan, regex=True)
        self.df['ts'] = dt.now()

    def _try_keyword_lat_lon(self, airport_data):
        """
        Add airport latitude and longitude information to pandas data frame 
        based on OpenAirports keywords.
        
        The function `add_lat_lon()` matches based on IATA codes. For those 
        airports without an IATA code, this function uses OpenAirport keywords 
        to match the airport information.
        
        Args:
            airport_data: OpenAirports information passed from `add_lat_lon()`
        """
        
        # key is airport columns
        # value is self.df columns
        LEG_DATA = {
            'dep_iata': {'ident': 'ident_dep',
                         'name': 'name_dep',
                         'lat': 'lat_dep',
                         'lon': 'lon_dep',
                         'iso_country': 'iso_country_dep',
                         'municipality': 'municipality_dep'},
            'arr_iata': {'ident': 'ident_arr',
                         'name': 'name_arr',
                         'lat': 'lat_arr',
                         'lon': 'lon_arr',
                         'iso_country': 'iso_country_arr',
                         'municipality': 'municipality_arr'},
        }
        
        for leg in LEG_DATA:
            narows = self.df[LEG_DATA[leg]['lat']].isna()
            
            # Taking only last four characters as added 'K' to denote
            # using keyword column
            idents = self.df.loc[narows, leg].apply(lambda x : x[-4:]).to_list()
            self.logger.debug(f"Finding for {leg} {LEG_DATA[leg]}:\n{idents}")

            res_rows = airport_data['keywords'].str.contains('|'.join(idents), na=False)
            res = airport_data.loc[res_rows, :]
            self.logger.debug(f"res:\n{res}")
            
            to_cols = [
                LEG_DATA[leg]['name'],
                LEG_DATA[leg]['lat'],
                LEG_DATA[leg]['lon'],
                LEG_DATA[leg]['iso_country'],
                LEG_DATA[leg]['municipality'],
            ]
            
            from_cols = [
                'name',
                'lat',
                'lon',
                'iso_country',
                'municipality',
            ]

            self.logger.debug(f"Using info\n{airport_data.loc[res_rows, from_cols]}")
            self.df.loc[narows, to_cols] = airport_data.loc[res_rows, from_cols].values
            self.logger.debug(f"updated row\n{self.df.loc[narows, to_cols]}")
        
        self.df = self.df.replace(r'^\s*$', np.nan, regex=True)


    def add_lat_lon(self):
        """
        Add airport latitude and longitude information to pandas data frame
        """
        airport_data = airport.get_airport_data()
        airport_data = airport_data[
            ['ident',
             'name',
             'latitude_deg',
             'longitude_deg',
             'iso_country',
             'municipality',
             'iata_code',
             'keywords']]
        
        airport_data = airport_data.rename(columns={
            'latitude_deg': 'lat',
            'longitude_deg': 'lon',
        })
        
        self.logger.debug(f"\n{airport_data.dtypes}")

        self.df = self.df.join(
            airport_data.loc[:, airport_data.columns != 'keywords'].set_index('iata_code'),
            how='left',
            on='dep_iata',
            lsuffix='_org',
            rsuffix='_dep')

        self.df = self.df.join(
            airport_data.loc[:, airport_data.columns != 'keywords'].set_index('iata_code'),
            how='left',
            on='arr_iata',
            lsuffix='_dep',
            rsuffix='_arr')
        
        self.df = self.df.rename(columns={
            'name': 'name_arr',
        })
        
        self.df = self.df.replace(r'^\s*$', np.nan, regex=True)
        self.logger.debug(f"Have added airport lat and lon data now have:\n{self.df.dtypes}")

        self._try_keyword_lat_lon(airport_data)

    def _return_empty_tz_dict(self, row):
        tz = EMPTY_TZ_DICT
        for key in EMPTY_TZ_DICT:
            if key in row:
                tz[key] = row[key]
        self.logger.debug(f"tz now:\n{tz}\n")
        return tz

    def _add_tz(self, row, gnusername, legs=DEFAULT_LEGS):
        gn = GeoNames(username=gnusername)
        
        valid_date_pat = re.compile('\\d{4}-\\d{2}-\\d{2}')
        self.logger.debug(f"row\n{row}")
        for leg in legs:
            tzid_col = f"{leg}_tzid"
            gmtoffset_col = f"{leg}_gmtoffset"
            
            lat = row[legs[leg]['lat']]
            lon = row[legs[leg]['lon']]
            date = row[legs[leg]['date']]
            self.logger.debug(f"find_tz for `{leg}`: `{lat}` `{lon}` `{date}`")
            
            valid_posn = not(math.isnan(lat) or math.isnan(lon))
            valid_date = valid_date_pat.match(str(date))
            
            if valid_date and valid_posn:
                self.logger.debug(f"Valid formats for {date};"
                                  f" lat/lon {lat},{lon}")
                try:
                    tz = gn.find_tz(lat,
                                    lon,
                                    date,
                                    timeout=3,
                                    maxretries=5)
                except GeoNamesDateReturnError:
                    self.logger.info(f"GeoNamesDateReturnError; using EMPTY_TZ_DICT")
                    tz = self._return_empty_tz_dict(row)
            else:
                if not valid_date:
                    self.logger.debug(f"Invalid date format for {date};"
                                     " using EMPTY_TZ_DICT")
                else:
                    self.logger.debug(f"Invalid lat/lon format for {lat},{lon};"
                                     " using EMPTY_TZ_DICT")
                tz = self._return_empty_tz_dict(row)

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
        self.logger.debug(f"add_timezones()")
        updated_flights = 0
        
        fill_rows = self.df['dt_info'] == DT_INFO_YMDT 
        self.df.loc[fill_rows, 'dep_date_str'] = \
            self.df.loc[fill_rows, 'dep_time'].dt.strftime('%Y-%m-%d')
        self.df.loc[fill_rows, 'arr_date_str'] = \
            self.df.loc[fill_rows, 'arr_time'].dt.strftime('%Y-%m-%d')

        fill_rows = (self.df['dt_info'] == DT_INFO_YMD)
        self.df.loc[fill_rows, ['dep_date_str', 'arr_date_str']] = \
            self.df.loc[fill_rows, 'date']

        # self.df.loc[~ymdt_rows, ['dep_date_str', 'arr_date_str']] = pd.NaT

        tz_cols = ['dep_tzid',
                   'dep_gmtoffset',
                   'arr_tzid',
                   'arr_gmtoffset']
        new_cols = list(set(tz_cols).difference(self.df.columns))
        if not new_cols:
            self.logger.debug(f"No new_cols to add")
        else:
            self.logger.debug(f"Adding new_cols: {new_cols}")
            for new_col in new_cols:
                self.df[new_col] = ''

        if num_flights is None:
            num_flights = len(self.df.index) + 1
        for index, row in self.df.iterrows():
            if updated_flights >= num_flights:
                break

            self.logger.debug(f"row is:\n{row[tz_cols]}\n{row[tz_cols].dtypes}")
            if type(row[tz_cols[0]]) is str:
                blank_row_test = (row[tz_cols[0]] == '') and \
                    (row['dep_time'] is not None)
            else:
                blank_row_test = math.isnan(row[tz_cols[0]]) & \
                    pd.notna(row['dep_time'])

            valid_date_pat = re.compile('\\d{4}-\\d{2}-\\d{2}')
            date_cols = ['dep_date_str', 'arr_date_str']
            valid_date_test = True
            for date_col in date_cols:
                date_to_check = row[date_col]
                valid_date = valid_date_pat.match(str(date_to_check))
                if not valid_date and valid_date_test:
                    valid_date_test = False
                    
                self.logger.debug(f"For date `{date_to_check}` "
                                 f"pattern match is `{valid_date}` "
                                 f"updated valid_date_test to {valid_date_test}")

            if all([update_blanks_only, blank_row_test, valid_date_test]):
                try:
                    self.logger.debug(f"Updating index {index}")
                    row = self._add_tz(row, gnusername=gnusername)
                    for tz_col in tz_cols:
                        self.df.loc[index, tz_col] = row[tz_col]

                except GeoNamesStopError as err:
                    self.logger.error(f"stopping due to:\n{err}")
                
                updated_flights += 1
                self.logger.info(f"Updated index {index}; "
                                 f"have now updated {updated_flights} flights")
            else:
                self.logger.debug(
                    f"Skipping index {index} due to "
                    f"update_blanks_only `{update_blanks_only}` "
                    f"blank_row_test `{blank_row_test}` "
                    f"valid_date_test `{valid_date_test}` ")
                next

    def save_pandas_to_csv(self, save_fp='flights.csv'):
        """
        Save pandas data frame to csv
        
        Args:
            save_path: Directory to save file to
            save_fn: File name to save file as
        """
        utils.check_create_path(save_fp)
        fp = Path(save_fp)
        self.logger.info(f"Saving self.df to {fp}")
        self.df.to_csv(fp, index=False)
    
    def read_pandas_from_csv(self, read_fp, save_fn='flights.csv'):
        """
        Read in csv to pandas data frame
        
        Args:
            save_path: Directory to find file in
            save_fn: File name read in
        """
        fp = Path(read_fp)
        self.logger.info(f"Reading self.df from {fp}")
        datetime_cols = [
            'date_as_dt',
            'dep_time',
            'arr_time',
            'dep_date_str',
            'arr_date_str',
            'ts',
        ]
        timedelata_cols = [
            'duration'
        ]
        col_types = {
            'flight_index': str,
            'dep_iata': str,
            'dep_city_county_name': str,
            'arr_iata': str,
            'arr_city_county_name': str,
            'date': str,
            # 'dep_time': dt,
            # 'arr_time': dt,
            'dt_info': str,
            'dist': int,
            'dist_units': str,
            # 'duration': td,
            'reason': str,
            'role': str,
            'seat': str,
            'class': str,
            'airplane': str,
            'reg': str,
            'name_org': str,
            'airline': str,
            'flightnum': str,
            # 'date_as_dt': dt,
            # 'ts': dt,
            'ident_dep': str,
            'name_dep': str,
            'lat_dep': float,
            'lon_dep': float,
            'iso_country_dep': str,
            'municipality_dep': str,
            'ident_arr': str,
            'name_arr': str,
            'lat_arr': float,
            'lon_arr': float,
            'iso_country_arr': str,
            'municipality_arr': str,
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


    def remove_rows(self, dbf, daf):
        
        if dbf and daf:
            self.logger.info("Removing rows between dates "
                             f"dbf: {dbf} daf: {daf}")
            rdrop = self.df[
                (self.df['date_as_dt'] >= daf) & (self.df['date_as_dt'] <= dbf)].index
        elif dbf:
            self.logger.info("Removing dates before "
                             f"dbf: {dbf}")
            rdrop = self.df[(self.df['date_as_dt'] <= dbf)].index
        elif daf:
            self.logger.info("Removing dates after "
                             f" daf: {daf}")
            rdrop = self.df[(self.df['date_as_dt'] >= daf)].index
        else:
            self.logger.info("No valid date ranges to remove "
                             f"dbf: {dbf} daf: {daf}")
            rdrop = None

        if rdrop is not None:
            self.logger.info(f"Removing {len(rdrop)} rows")
            self.df = self.df.drop(rdrop)


    def insert_updated_rows(self, fd_updated):
        self.logger.debug(f"self has types:\n{self.df.dtypes}")
        self.logger.debug(f"fd_updated has types:\n{fd_updated.df.dtypes}")
        
        on_cols = [
            'dep_iata',
            'dep_city_county_name',
            'arr_iata',
            'arr_city_county_name',
            'date',
            'dep_time',
            'arr_time',
            'dt_info',
            'dist',
            'dist_units',
            'duration',
            'reason',
            'role',
            'seat',
            'class',
            'airplane',
            'reg',
            'name_org',
            'airline',
            'flightnum',
            'date_as_dt',
            'ident_dep',
            'name_dep',
            'lat_dep',
            'lon_dep',
            'iso_country_dep',
            'municipality_dep',
            'ident_arr',
            'name_arr',
            'lat_arr',
            'lon_arr',
            'iso_country_arr',
            'municipality_arr',]
        
        # Replacing np.nan with empty strings; to to revert back later
        self.df = self.df.fillna(value='')
        fd_updated.df = fd_updated.df.fillna(value='')

        # Sometimes end up with mixed type cols, so reverting to str for those
        # that can be mixed
        to_str_cols = [
            'lat_dep',
            'lon_dep',
            'lat_arr',
            'lon_arr']
        self.df[to_str_cols] = self.df[to_str_cols].astype(str)
        fd_updated.df[to_str_cols] = fd_updated.df[to_str_cols].astype(str)

        exc_cols = ['flight_index']
        df_all = self.df.merge(
            fd_updated.df.loc[:, ~fd_updated.df.columns.isin(exc_cols)],
            on=on_cols,
            how='outer',
            indicator=True)
        
        df_all.loc[df_all['ts_x'].isna(), 'ts_x'] = df_all.loc[df_all['ts_x'].isna(), 'ts_y']
        df_all.drop(columns=['ts_y', '_merge'], inplace=True)
        df_all.rename(
            columns={'ts_x': 'ts'},
            inplace=True,
            errors='raise',
            )

        sort_cols = ['date', 'dep_time', 'arr_time']
        self.df = df_all.sort_values(by=sort_cols)
        self.df['flight_index'] = range(1, len(self.df.index) + 1)
        
        self.logger.debug(f"Have inserted new data; now have:\n{self.df.dtypes}")
                
        # Need to replace empty str with np.nan
        non_str_cols = ['lat_dep',
                        'lon_dep',
                        'lat_arr',
                        'lon_arr',
                        'dep_gmtoffset',
                        'arr_gmtoffset',]
        self.df[non_str_cols] = self.df[non_str_cols].replace(r'^\s*$', np.nan, regex=True)        
        self.df[non_str_cols] = self.df[non_str_cols].astype(float)

        self.logger.debug(f"Have replaced empty str now have:\n{self.df.dtypes}")
