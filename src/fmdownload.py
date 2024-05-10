import io
import sys
from bs4 import BeautifulSoup as bs
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support.select import Select
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

import logins
import data
import utils
import dataexport
import fmvalidate

from constants import DT_INFO_YMDT, DT_INFO_YMDO, DT_INFO_YMD, DT_INFO_YM, DT_INFO_Y
from constants import STR_TYPE_LU, DT_FMTS, KM_TO_MILES
from constants import CLASS_OPENFLIGHTS_LU, SEAT_OPENFLIGHTS_LU, REASON_OPENFLIGHTS_LU
from constants import CLASS_MYFLIGHTPATH_LU, REASON_MYFLIGHTPATH_LU

import fmplanelu

mpath = Path(__file__).parent.absolute()

APP_NAME = 'fmsave'
_module_logger_name = f'{APP_NAME}.{__name__}'
module_logger = logging.getLogger(_module_logger_name)
module_logger.info(f"Module {_module_logger_name} logger initialized")


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
        self.fms_data_dict = data.get_yaml('fmsave', 'fmsave', logger=self.logger)

        # hold login status
        self.logged_in = False
        self.fm_pw = None
        self.fm_un = None


    def login(self,
              username=None,
              password=None,
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
        
        if username is None: username = self.fm_un
        if password is None: password = self.fm_pw

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
            self.logged_in = True
        except TimeoutException:
            self.logger.error("TimeoutException: Assuming wrong credentials; exiting")
            sys.exit()


    def _get_number_of_pages(self):
        select_element = self.driver.find_element(By.XPATH, '//select[@name="dbpos"]')
        select = Select(select_element)
        return len(select.options)


    def _get_outer_html(self):
        WDSCRIPT_OUTER_HTML = 'return document.documentElement.outerHTML'
        self.pages.append(self.driver.execute_script(WDSCRIPT_OUTER_HTML))


    def _get_next_page(self, last_page_timeout=10):
        WebDriverWait(self.driver, last_page_timeout)\
            .until(EC.element_to_be_clickable(
                (By.XPATH, "//img[contains(@src,'/images/next.gif')]")
                )).click()


    def get_fm_pages(self, max_pages=None, last_page_timeout=5):
        """
        Get html pages from Flight Memory website
        
        Args:
            max_pages: Maximum number of pages to get
            last_page_timeout: How long to wait for the 'next.gif' load; if 
            timeout exceeded, then assumed we are at the last page
        """

        loop_counter = 0
        pages_len = len(self.pages)
        num_pages_on_fm = self._get_number_of_pages()
        self.logger.info(f"There are {num_pages_on_fm} pages to download from FM")

        if max_pages is None:
            max_pages = num_pages_on_fm

        utils.percent_complete(loop_counter, max_pages)
        while loop_counter < max_pages:
            loop_counter += 1
            self.logger.debug(f"Getting page number: {loop_counter}")
            self._get_outer_html()

            if loop_counter < max_pages:
                try:
                    self._get_next_page(last_page_timeout)
                    self.logger.debug(f"Found page for next loop at counter {loop_counter}")

                except TimeoutException:
                    self.logger.info(f"TimeoutException; ending at loop {loop_counter}")
                    break
            
            utils.percent_complete(loop_counter, max_pages)

        print("\n")
        self.logger.debug(f"Exited loop as hit max for at {loop_counter}")

        found_pages = len(self.pages) - pages_len
        pages_len = len(self.pages)
        self.logger.info(f"Found {found_pages} pages and read {pages_len} in")


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

        self.logger.info(f"Saved {page_num + 1} pages to {save_path}")


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
            
            with open(page_file, 'r', encoding='utf-8') as f:
                self.pages.append(f.read())
        
        self.logger.info(f"Have read in {len(self.pages)} pages")


    def _split_date_col(self):
        # Column has the following formats
        # Year only: YYYY or in regex r'^\d{4}'
        # Date only: DD-MM-YYYY or r'^\d{2}\.\d{2}\.\d{4}$'
        # Date with time: DD-MM-YYYY HH:MM or r'^\d{2}\.\d{2}\.\d{4}\s+\d{2}\:\d{2}$'
        # Date, time with day offset: DD-MM-YYYY HH:MM +/-D or 
        # r'^\d{2}\.\d{2}\.\d{4}\s+\d{2}\:\d{2}\s+\d{2}\:\d{2}\s+(?:\+|\-)\d)$'
        # Date with day offset: DD-MM-YYYY +/-D or r'^\d{2}\.\d{2}\.\d{4}\s+(?:\+|\-)\d)$'
        # Note there may be multiple spaces due to the collapsing of new lines
        
        # For the date with day offset case, need to ensure there are three
        # spaces for when we split into four columns
        pat = r'^(\d{2}\.\d{2}\.\d{4})\s+((?:\+|\-)\d)'
        repl = r'\1   \2'
        self.df['date_dept_arr_offset'] = self.df['date_dept_arr_offset']\
            .str.replace(pat=pat, repl=repl, regex=True)
        
        expected_cols = 4
        str_split = self.df['date_dept_arr_offset']\
            .str.split(' ', expand=True, n=expected_cols)
        
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
             'time_dep',
             'time_arr',
             'date_offset']] = str_split

        self.df['dt_info'] = None

        # year, month, day and time available
        condition = self.df['time_dep'].str.len() > 0
        self.df.loc[condition, 'dt_info'] = DT_INFO_YMDT
        
        # year, month, day and offset available, but no time
        condition = ~self.df['date_offset'].isna() & self.df['dt_info'].isna()
        self.df.loc[condition, 'dt_info'] = DT_INFO_YMDO
        self.df.loc[condition, 'time_dep'] = None
        self.df.loc[condition, 'time_arr'] = None

        # rearrange date by putting year first
        pat = r'(\d{2})\.(\d{2})\.(\d{4})'
        repl = r'\3-\2-\1'
        condition = ~self.df['dt_info'].isna()
        self.df.loc[condition, 'date'] = self.df.loc[condition, 'date']\
            .str.replace(pat=pat, repl=repl, regex=True) 
        
        # year, month, day only available
        pat = r'(\d{2})\.(\d{2})\.(\d{4})'
        condition = (self.df['dt_info'].isna()) & (self.df['date'].str.match(pat))
        self.df.loc[condition, 'dt_info'] = DT_INFO_YMD
        
        repl = r'\3-\2-\1'
        self.df.loc[condition, 'date'] = self.df.loc[condition, 'date']\
            .str.replace(pat=pat, repl=repl, regex=True)

        # year, month only available
        pat = r'(\d{2})\.(\d{4})'
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
        self.df[
            ['dist',
             'dist_units',
             'duration',
             'duration_units']] = self.df['dist_duration']\
                 .str.split('\\|\\|', expand=True)
        self.df['dist'] = pd.to_numeric(self.df['dist'].str.replace(',', ''))


    def _split_seat_col(self):
        SEAT_POSITIONS = ['Window', 'Aisle', 'Middle']
        CLASS = ['Economy', 'EconomyPlus', 'Business', 'First']
        ROLE = ['Passenger', 'Crew', 'Cockpit']
        REASON = ['Personal', 'Business', 'virtuell']

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
            'seat_position',
            'class',
            'role',
            'reason']] = str_split
                 
        self.df[['seat', 'position']] = self.df['seat_position']\
            .str.split('\\/', expand=True)
        
        move_col_rows = self.df['class'].isin(ROLE)
        self.df.loc[move_col_rows, 'reason'] = self.df.loc[move_col_rows, 'role']
        self.df.loc[move_col_rows, 'role'] = self.df.loc[move_col_rows, 'class']
        self.df.loc[move_col_rows, 'class'] = ''


    def _split_airplane_col(self):
        pat = '(?>\\s|^)('  # start of string 
        pat += '(?>N\\w{3,5})'  # for USA registrations
        pat += '|(?>(?>HI|HL|JA|JR|UK|UR|YV)\\w{2,5})'  # for registrations with two letter prefix and four digit suffix, no dash
        pat += '|(?>(?>2|B|C|D|F|G|I|M|P|U|Z)-\\w{2,5})'  # for registrations with single letter prefix
        pat += '|(?>(?>3|4|5|6|7|8|9)[A-Z]-\\w{2,5})'  # for registrations with a prefix starting with a number then a letter
        pat += '|(?>(?>C|D|E|H|J|L|O|P|R|S|T|U|V|X|Y|Z)\\w-\\w{2,5})'  # for registrations with a prefix starting with a letter from C onwards, then a number or a letter
        pat += '|(?>A(?>[P2-8])-\\w{2,5})'  # for registrations with a prefix starting with `A` then a number or a letter
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
            ['airplane_type',
             'airplane_reg',
             'airplane_name']] = str_split


    def _add_airplane_types(self):
        data_format = 'wiki'
        data_set = 'aircraft'

        match_col = 'airplane_type'
        check_col = 'icao_type'

        data_dict = data.get_yaml(data_format, data_set, self.logger)
        col_names = utils.get_data_dict_column_names(data_dict, data_set)
        col_types = utils.get_parents_with_key_values(
            data_dict,
            key='type',
            values=['float', 'str'])
        col_types = utils.replace_item(col_types, STR_TYPE_LU)
        
        wiki_data = data.get_wiki_data(data_set, names=col_names, dtype=col_types)

        self.df[match_col] = self.df[match_col].fillna('')
        self.df = data.fuzzy_merge(self.df, wiki_data, match_col, 'model_name', limit=1)

        self.df = self.df.join(
            wiki_data.set_index('model_name'),
            how='left',
            on='matches',)

        self.df.drop(['matches'], axis=1, inplace=True)

        row_filter = self.df[check_col].isna()
        mismatch_values = sorted(self.df.loc[row_filter, match_col].unique())

        display_cols = col_names

        col_widths = [
            9,
            9,
            50,
        ]

        for mmv in mismatch_values:
            if mmv is None or len(mmv) == 0:
                continue

            find_str = str(mmv)
            sel_row = data.select_fuzzy_match(
                wiki_data,
                find_str,
                'model_name',
                display_cols,
                col_widths,
                logger=self.logger,)
            
            if sel_row is None:
                continue
            else:
                self.df.loc[self.df[match_col] == find_str, check_col] = sel_row[check_col].values[0]


    def _split_airline_col(self):
        pat = r'(\w{2}\d{1,4})$'
        self.df['flightnum'] = self.df['airline_flightnum']\
            .str.extract(pat, expand=True)

        self.df['iata_airline'] = self.df['flightnum'].str.slice(0, 2)
        
        pat = r'(.+) ' + pat
        repl = r'\1'
        self.df['airline'] = self.df['airline_flightnum']\
            .str.replace(pat=pat, repl=repl, regex=True)


    def _dates_to_dt(self):
        time_cols = utils.get_parents_for_keys_with_value(self.fms_data_dict, 'time')
        self.logger.debug(
            f"\n{self.df.loc[0, ['date', 'time_dep', 'time_arr', 'date_offset']]}")

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
        self.df['time_arr'] = self.df['time_arr'] \
            + self.df['date_offset']


    def _duration_to_td(self):
        dur_hr_min = self.df['duration']\
            .str.split(':', expand=True).astype(int)
        self.df['duration'] = pd.to_timedelta(dur_hr_min[0], unit='h') + \
            pd.to_timedelta(dur_hr_min[1], unit='m')


    def _comments_detailurl(self):
        pat = r'Note '
        self.df['comments'] = self.df['comments_detail_url']\
            .str.contains(pat=pat, regex=True)


    def get_comments(self, filter_col=None):
        if not self.logged_in:
            self.logger.info("Found comments to download; need to login to flightmemory.com")
            if self.fm_un is None: self.fm_un = logins.get_fm_un()
            if self.fm_pw is None: self.fm_pw = logins.get_fm_pw()
            self.login()

        loop_counter = 0
        filter_cols = [filter_col, 'comments'] if filter_col else ['comments']
        urls = self.df.loc[self.df[filter_cols].all(axis=1), 'detail_url']
        num_urls = len(urls)
        self.logger.debug(f"Have {num_urls} urls to get")
        utils.percent_complete(loop_counter, num_urls)
        for url in urls:
            self.logger.debug(f"Getting url {loop_counter + 1} out of {num_urls}: {url}")
            self.driver.get(url)
            comment = self.driver.find_element(By.NAME, 'kommentar').text
            self.df.loc[self.df['detail_url'] == url, 'comment'] = comment
            loop_counter += 1
            utils.percent_complete(loop_counter, num_urls)
        print("\n")
        self.df['comment'] = self.df['comment'].str.replace(r'\n', '', regex=True)


    def links_from_options(self, table):
        BASE_URL = 'https://www.flightmemory.com/signin/'
        links = []
        for tr in table.findAll('tr'):
            trs = tr.findAll('td')
            if len(trs) > 0:
                link = trs[-1].find_all(lambda t: t.name == 'option' and re.compile("edit"))[1]
                links.append(BASE_URL + link.get('value'))
        
        return links


    def _get_date_filter(self, dates_before, dates_after):
        # date_filter = pd.Series(data=[True]*len(self.df.index), dtype='boolean')
        self.df['date_filter'] = True
        if dates_before:
            self.df['date_filter'] = self.df['date_as_dt'] <= dates_before

        if dates_after:
            self.df['date_filter'] = (self.df['date_as_dt'] >= dates_after) & self.df['date_filter']


    def fm_pages_to_pandas(self, dates_before=None, dates_after=None):
        """
        Convert Flight Memory web pages to pandas data frame
        
        Once dates are determined, only update comments for flights that match
        the date criteria
        
        Args:
            dates_before: Only get comments for flights before this date; as datetime
            dates_after: Only get comments for flights before this date; as datetime
        """
        for idx, page in enumerate(self.pages):
            self.logger.debug(f"Reading page {idx+1} to self.df")
            flight_tbl = _get_str_for_pd(page)
            df = pd.read_html(
                    io.StringIO(str(flight_tbl)),
                    flavor='bs4',)[0]
            df['detail_url'] = self.links_from_options(flight_tbl)
            self.df = pd.concat([self.df, df],
                                        ignore_index=True)

        self.logger.info(f"Finished reading in {idx+1} pages; "
                         f"read in {len(self.df.index):,} flights")

        self.df.rename(
            columns={
                self.df.columns[0]: 'flight_index',
                self.df.columns[1]: 'date_dept_arr_offset',
                self.df.columns[2]: 'iata_dep',
                self.df.columns[3]: 'city_county_name_dep',
                self.df.columns[4]: 'iata_arr',
                self.df.columns[5]: 'city_county_name_arr',
                self.df.columns[6]: 'dist_duration',
                self.df.columns[7]: 'airline_flightnum',
                self.df.columns[8]: 'airplane_reg_name',
                self.df.columns[9]: 'seat_class_place',
                self.df.columns[10]: 'comments_detail_url',
                },
            inplace=True,
            errors='raise',
            )
        self._split_date_col()
        self._dates_to_dt()
        self.keep_rows_by_date(dates_before, dates_after)

        self._split_dist_col()
        self._split_seat_col()
        self._split_airplane_col()
        self._add_airplane_types()
        self._split_airline_col()
        self._duration_to_td()
        self._comments_detailurl()
        self._get_date_filter(dates_before, dates_after)

        comments = self.df.loc[self.df['date_filter'], 'comments']
        self.df['comment'] = ''
        self.logger.info(f"We have {comments.sum()} notes")
        if comments.sum() > 0:
            self.get_comments('date_filter')

        self.df.drop(columns=['date_filter'], inplace=True)
        self.df.drop(['date_dept_arr_offset',
                      'dist_duration',
                      'seat_class_place',
                      'airplane_reg_name',
                      'airline_flightnum',
                      'seat_position',
                      'date_offset',
                      'duration_units',
                      'comments_detail_url'],
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

        values = ['ident', 'name', 'lat', 'lon', 'iso_country', 'municipality']
        data_keys =  utils.get_parents_with_key_values(self.fms_data_dict, 'data', values)

        legs = ['dep', 'arr']
        leg_data = {}

        for leg in legs:
            data_leg_keys = utils.find_keys_containing(data_keys, leg)
            leg_key = utils.get_parents_for_keys_with_all_values(
                self.fms_data_dict, ['iata', leg])[0]
            leg_data[leg_key] = data_leg_keys[leg]
        
        for leg in leg_data:
            narows = self.df[leg_data[leg]['lat']].isna()
            
            # Taking only last four characters as added 'K' to denote
            # using keyword column
            idents = self.df.loc[narows, leg].apply(lambda x : x[-4:]).to_list()
            self.logger.debug(f"Finding for {leg} {leg_data[leg]}:\n{idents}")

            res_rows = airport_data['keywords'].str.contains('|'.join(idents), na=False)
            res = airport_data.loc[res_rows, :]
            
            to_cols = [
                leg_data[leg]['name'],
                leg_data[leg]['lat'],
                leg_data[leg]['lon'],
                leg_data[leg]['iso_country'],
                leg_data[leg]['municipality'],
            ]
            
            from_cols = [
                'name',
                'lat',
                'lon',
                'iso_country',
                'municipality',
            ]

            self.df.loc[narows, to_cols] = airport_data.loc[res_rows, from_cols].values
        
        self.df = self.df.replace(r'^\s*$', np.nan, regex=True)


    def _fuzzy_match_airports(self, airport_data, filter_col=None):
        row_filter = self.df[['lat_dep', 'lat_arr']].isna().any(axis=1)
        if filter_col: row_filter = row_filter & self.df[filter_col]
        mismatch_rows = self.df.loc[row_filter, :]
        self.logger.debug(f"There are {len(mismatch_rows)} mismatches")
        
        df = airport_data
        df = df.rename(columns={'iata_code': 'iata'})
        
        display_cols = [
            'iata',
            'icao',
            'name',
            'iso_country',
            'municipality',
            'keywords',
            ]

        col_widths = [
            4,
            7,
            30,
            11,
            15,
            30,
        ]

        update_cols = [
            'ourairports_id',
            'iata',
            'icao',
            'name',
            'lat',
            'lon',
            'iso_country',
            'municipality',
            ]

        for mmidx, mm in mismatch_rows.iterrows():
            for leg in ['_dep', '_arr']:
                if math.isnan(mm['lat' + leg]):
                    find_str = mm['city_county_name' + leg]
                    sel_row = data.select_fuzzy_match(
                        df, find_str, 'name', display_cols,
                        col_widths, logger=self.logger)
                    
                    if sel_row is None:
                        continue
                    else:
                        for col in update_cols:
                            self.df.loc[mmidx, col + leg] = sel_row[col].values[0]


    def add_lat_lon(self, dates_before=None, dates_after=None):
        """
        Add airport latitude and longitude information to pandas data frame
        
        Only update comments for flights that match the date criteria
        
        Args:
            dates_before: Only get comments for flights before this date; as datetime
            dates_after: Only get comments for flights before this date; as datetime
        """
        airport_data = data.get_ourairport_data()

        airport_data = airport_data[
            ['id',
             'ident',
             'name',
             'latitude_deg',
             'longitude_deg',
             'iso_country',
             'municipality',
             'iata_code',
             'keywords']]
        
        airport_data = airport_data.rename(columns={
            'id': 'ourairports_id',
            'ident': 'icao',
            'latitude_deg': 'lat',
            'longitude_deg': 'lon',
        })
        exc_cols = ~airport_data.columns.isin(['keywords'])

        self.df = self.df.join(
            airport_data.loc[:, exc_cols].set_index('iata_code'),
            how='left',
            on='iata_dep',
            lsuffix='_org',
            rsuffix='_dep')

        self.df = self.df.join(
            airport_data.loc[:, exc_cols].set_index('iata_code'),
            how='left',
            on='iata_arr',
            lsuffix='_dep',
            rsuffix='_arr')
        
        self.df = self.df.rename(columns={
            'name': 'name_arr',
        })
        
        self.df = self.df.replace(r'^\s*$', np.nan, regex=True)
        self.logger.debug(f"Have added airport lat and lon data now have:\n{self.df.dtypes}")

        # If any of the latitude columns are na, then lets try using
        # keywords to match airport info
        self._get_date_filter(dates_before, dates_after)

        if self.df.loc[self.df['date_filter'], ['lat_dep', 'lat_arr']].isna().any(axis=1).sum():
            self.logger.debug("Trying fuzzy matching for airports")
            self._fuzzy_match_airports(airport_data, 'date_filter')

        self.df.drop(columns=['date_filter'], inplace=True)


    def _return_empty_tz_dict(self, row):
        tz = EMPTY_TZ_DICT
        for key in EMPTY_TZ_DICT:
            if key in row:
                tz[key] = row[key]
        self.logger.debug(f"tz now:\n{tz}\n")
        return tz


    def _add_tz(self, row, gnusername):
        gn = GeoNames(username=gnusername)
        
        values = ['date', 'lat', 'lon', 'tzid', 'gmtoffset']
        data_keys =  utils.get_parents_with_key_values(
            self.fms_data_dict, 'data', values)

        legs = ['dep', 'arr']
        leg_data = {}
        for leg in legs:
            leg_data[leg] = utils.find_keys_containing(data_keys, leg)[leg]
        
        self.logger.debug(f"leg_data is:\n{leg_data}")
        valid_date_pat = re.compile('\\d{4}-\\d{2}-\\d{2}')
        self.logger.debug(f"row\n{row}")
        for leg in leg_data:
            tzid_col = leg_data[leg]['tzid']
            gmtoffset_col = leg_data[leg]['gmtoffset']

            
            lat = row[leg_data[leg]['lat']]
            lon = row[leg_data[leg]['lon']]
            date = row[leg_data[leg]['date']]
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
                    self.logger.debug(f"GeoNamesDateReturnError; using EMPTY_TZ_DICT")
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
        updated_flights = 0
        
        # First get list of columns we're interested in using
        values = ['date', 'time', 'lat', 'lon', 'tzid', 'gmtoffset']
        data_keys =  utils.get_parents_with_key_values(
            self.fms_data_dict, 'data', values)
        legs = ['dep', 'arr']
        time_date_cols = {}
        for leg in legs:
            # While we're getting the columns, will also see which rows have
            # Year-Month-Day-Timezone information
            time_date_cols[leg] = utils.find_keys_containing(data_keys, leg)[leg]
            fill_rows = self.df['dt_info'] == DT_INFO_YMDT
            self.logger.debug(f"fill_rows {leg} YMDT is length {sum(fill_rows)}")
            
            if time_date_cols[leg]['date'] in self.df.columns:
                # Only want to fill rows where date is absent
                fill_rows = fill_rows & (self.df[time_date_cols[leg]['date']].isna())
                self.logger.debug(f"fill_rows {leg} YMDT is now length {sum(fill_rows)}")
            
            # Now fill the rows with the date info we have for this leg
            if sum(fill_rows):
                self.df.loc[fill_rows, time_date_cols[leg]['date']] = \
                    pd.to_datetime(
                        self.df.loc[
                            fill_rows,
                            time_date_cols[leg]['time']].dt.strftime('%Y-%m-%d'))

        # Can also get dates for where we have Year-Month-Day information
        fill_rows = (self.df['dt_info'] == DT_INFO_YMD)
        self.logger.debug(f"fill_rows YMD is length {sum(fill_rows)}")
        date_cols = [time_date_cols['dep']['date'],
                     time_date_cols['arr']['date']]
        if set(date_cols).issubset(set(self.df.columns)):
            # Again, only fill rows where date info is abset
            fill_rows = fill_rows & (self.df[date_cols].isna().any(axis=1))
            self.logger.debug(f"fill_rows YMD is now length {sum(fill_rows)}")

        if sum(fill_rows):
            self.df.loc[fill_rows, date_cols] = self.df.loc[fill_rows, 'date']

        # Now get timezone columns
        tz_cols = utils.get_parents_list_with_key_values(
            self.fms_data_dict, 'data', ['tzid', 'gmtoffset'])

        # See if we need to add columns
        new_cols = list(set(tz_cols).difference(self.df.columns))
        if not new_cols:
            self.logger.debug(f"No new_cols to add")
        else:
            self.logger.debug(f"Adding new_cols: {new_cols}")
            for new_col in new_cols:
                self.df[new_col] = ''

        # Determine which rows we want to update
        if update_blanks_only:
            rows_to_update = self.df[tz_cols].replace(
                '', np.nan, inplace=False).isna().any(axis=1)
            rows_to_update = rows_to_update & (
                (self.df['dt_info'] == DT_INFO_YMDT) | \
                    (self.df['dt_info'] == DT_INFO_YMD))
        else:
            rows_to_update = pd.Series(data=True, index=self.df.index)

        if num_flights is None:
            num_flights = sum(rows_to_update)

        self.logger.info(f"Adding time zones for {num_flights} flights")
        if num_flights == 0:
            self.logger.info(f"No flights to update so ending add timezones")
            return

        utils.percent_complete(updated_flights, num_flights)
        for index, row in self.df[rows_to_update].iterrows():
            self.logger.debug(f"updated_flights: {updated_flights} "
                             f"index: {index}")
            if updated_flights >= num_flights:
                break

            self.logger.debug(f"row is:\n{row[tz_cols]}\n{row[tz_cols].dtypes}")

            date_dt_cols = utils.get_parents_for_keys_with_all_values(self.fms_data_dict, ['dt', 'date'])
            date_dep_cols = utils.get_parents_for_keys_with_all_values(self.fms_data_dict, ['dep', 'date'])
            date_arr_cols = utils.get_parents_for_keys_with_all_values(self.fms_data_dict, ['arr', 'date'])
            date_cols = list(set(date_dt_cols) & (set(date_dep_cols) | set(date_arr_cols)))

            valid_date_pat = re.compile('\\d{4}-\\d{2}-\\d{2}')
            valid_date_test = True
            for date_col in date_cols:
                date_to_check = row[date_col]
                valid_date = valid_date_pat.match(str(date_to_check))
                if not valid_date and valid_date_test:
                    valid_date_test = False
                    
                self.logger.debug(
                    f"For date `{date_to_check}` "
                    f"pattern match is `{valid_date}` "
                    f"updated valid_date_test to {valid_date_test}")

            if all([update_blanks_only, valid_date_test]):
                try:
                    self.logger.debug(f"Updating index {index}")
                    row = self._add_tz(row, gnusername=gnusername)
                    for tz_col in tz_cols:
                        self.df.loc[index, tz_col] = row[tz_col]
                except GeoNamesStopError as err:
                    self.logger.error(f"Stopping due to:\n{err}")
                    break
                
                updated_flights += 1
                self.logger.debug(
                    f"Updated index {index}; "
                    f"have now updated {updated_flights} flights "
                    f"out of {num_flights}")
            else:
                self.logger.debug(
                    f"Skipping index {index} due to "
                    f"update_blanks_only `{update_blanks_only}` "
                    f"valid_date_test `{valid_date_test}` ")
                next
            
            utils.percent_complete(updated_flights, num_flights)


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
        self.df.to_csv(fp, index=False, encoding='utf-8')


    def read_pandas_from_csv(self, read_fp, save_fn='flights.csv'):
        """
        Read in csv to pandas data frame
        
        Args:
            save_path: Directory to find file in
            save_fn: File name read in
        """
        fp = Path(read_fp)
        self.logger.info(f"Reading self.df from {fp}")

        datetime_cols = utils.get_parents_for_keys_with_all_values(self.fms_data_dict, ['dt'])
        timedelata_cols = utils.get_parents_for_keys_with_all_values(self.fms_data_dict, ['td'])
                
        col_types = utils.get_parents_with_key_values(
            self.fms_data_dict,
            key='type',
            values=['float', 'str'])
        col_types = utils.replace_item(col_types, STR_TYPE_LU)
                
        self.df = pd.read_csv(fp, dtype=col_types)

        for col in datetime_cols:
            self.df[col] = pd.to_datetime(
                self.df[col], format='ISO8601', yearfirst=True)

        for col in timedelata_cols:
            self.df[col] = pd.to_timedelta(
                self.df[col])

        self.logger.debug(f"Have read in csv; df types:\n{self.df.dtypes}")


    def remove_rows_by_date(self, dbf=dt(2100, 12, 31), daf=dt(1900, 1, 1)):
        """
        Remove rows in self.df based on dates in column 'date_as_dt'
        
        Args:
            dbf: Remove rows that are on and before this date i.e., <= dbf
            daf: Remove rows that are on and after this date i.e., <= daf
        """
        if dbf is None:
            dbf = dt(2100, 12, 31)

        if daf is None:
            daf = dt(1900, 1, 1)

        self.logger.debug(f"Removing rows between dates {dbf} and {daf}")
        rdrop = self.df[
                (self.df['date_as_dt'] >= daf) & \
                    (self.df['date_as_dt'] <= dbf)].index

        self.logger.debug(f"Removing {len(rdrop)} rows")
        self.df = self.df.drop(rdrop)


    def keep_rows_by_date(self, dbf=dt(2100, 12, 31), daf=dt(1900, 1, 1)):
        """
        Keep rows in self.df based on dates in column 'date_as_dt'
        
        Args:
            dbf: Keep rows that are on and before this date i.e., <= dbf
            daf: Keep rows that are on and after this date i.e., <= daf
        """
        if dbf is None:
            dbf = dt(2100, 12, 31)

        if daf is None:
            daf = dt(1900, 1, 1)

        self.logger.debug(f"Keeping rows between dates {dbf} and {daf}")
        rkeep = self.df[
                (self.df['date_as_dt'] >= daf) & \
                    (self.df['date_as_dt'] <= dbf)].index

        self.logger.debug(f"Keeping {len(rkeep)} rows")
        self.df = self.df.iloc[rkeep, :]


    def insert_updated_rows(self, fd_updated):
        on_cols = utils.get_parents_list_with_key_values(
            self.fms_data_dict,
            key='update_merge_on',
            values=[True])
        
        # Replacing np.nan with empty strings; to to revert back later
        self.df = self.df.fillna(value='')
        fd_updated.df = fd_updated.df.fillna(value='')

        # Sometimes end up with mixed type cols, so reverting to str for those
        # that can be mixed
        to_str_cols = utils.get_parents_list_with_key_values(
            self.fms_data_dict, 'data', ['lon', 'lat', 'ourairports_id'])

        self.df[to_str_cols] = self.df[to_str_cols].astype(str)
        fd_updated.df[to_str_cols] = fd_updated.df[to_str_cols].astype(str)

        exc_cols = ['flight_index']
        self_dyptes = set(self.df.columns.to_list())
        self.logger.debug(f"self has types:\n{self.df.dtypes}")
        
        fd_updated_dtypes = fd_updated.df.columns.to_list()
        self.logger.debug(f"fd_updated has types:\n{fd_updated.df.dtypes}")
        
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
        sort_cols = ['date', 'time_dep', 'time_arr']

        self.df = df_all.sort_values(by=sort_cols)
        self.df['flight_index'] = range(1, len(self.df.index) + 1)

        self.logger.debug(f"Have inserted new data; now have:\n{self.df.dtypes}")
                
        non_str_cols = to_str_cols
        self.df[non_str_cols] = self.df[non_str_cols].replace(r'^\s*$', np.nan, regex=True)        
        self.df[non_str_cols] = self.df[non_str_cols].astype(float)

        self.logger.debug(f"Have replaced empty str now have:\n{self.df.dtypes}")


    def validate_distance_times(self):
        self.df['dist_validated'] = fmvalidate.calc_distance(self.df, 'lat_dep', 'lon_dep', 'lat_arr', 'lon_arr')
        self.df['dist_pct_err'] = (self.df['dist'] - self.df['dist_validated']) / self.df['dist'] * 100
        self.df['dist_pct_err'] = self.df['dist_pct_err'].abs()
        
        self.df['duration_validated'] = fmvalidate.calc_duration(self.df, 'time_dep', 'time_arr', 'gmtoffset_dep', 'gmtoffset_arr')
        self.df['dur_pct_err'] = (self.df['duration'] - self.df['duration_validated']) / self.df['duration'] * 100
        self.df['dur_pct_err'] = self.df['dist_pct_err'].abs()


    def _export_to_openflights(self, fsave):
        exp_format = 'openflights'
        exp_df = dataexport.match_openflights_airports(self.df, self.logger)
        exp_df = dataexport.match_openflights_airlines(exp_df, self.logger)

        exp_data_dict = data.get_yaml(exp_format, exp_format, logger=self.logger)
        col_renames = utils.get_parents_with_key_values(exp_data_dict, 'fmcol', [r'^.+$'], True)
        col_renames = utils.swap_keys_values(col_renames)

        for fmt in DT_FMTS.keys():
            fmt_rows = exp_df['dt_info'] == fmt
            dt_dmt = DT_FMTS[fmt]['fmt']
            dt_col = DT_FMTS[fmt]['srccol']
            exp_df.loc[fmt_rows, 'date_as_str'] = exp_df.loc[fmt_rows, dt_col].dt.strftime(dt_dmt)

        exp_cols = utils.get_keys(col_renames)
        exp_cols = [x for x in exp_cols if x in set(exp_df.columns)]
        exp_df = exp_df[exp_cols].rename(columns=col_renames)

        exp_df['Duration'] = exp_df['Duration'].dt.to_pytimedelta().astype('str')
        exp_df['Distance'] = exp_df['Distance'] * KM_TO_MILES
        exp_df['Distance'] = exp_df['Distance'].astype('int64')
        exp_df['Class'] = exp_df['Class'].replace(CLASS_OPENFLIGHTS_LU)
        exp_df['Reason'] = exp_df['Reason'].replace(REASON_OPENFLIGHTS_LU)
        exp_df['Seat_Type'] = exp_df['Seat_Type'].replace(SEAT_OPENFLIGHTS_LU)
        
        col_loc = exp_df.columns.get_loc('Registration') + 1
        exp_df.insert(loc=col_loc, column='Trip', value='')

        exp_df.to_csv(fsave, index=False, encoding='utf-8')
        self.logger.info(f"Finished exporting with format `{exp_format}` to `{fsave}`")


    def _export_to_myflightpath(self, fsave):
        exp_format = 'myflightpath'

        exp_df = self.df

        exp_data_dict = data.get_yaml(exp_format, exp_format, logger=self.logger)
        col_renames = utils.get_parents_with_key_values(exp_data_dict, 'fmcol', [r'^.+$'], True)
        col_renames = utils.swap_keys_values(col_renames)

        for fmt in DT_FMTS.keys():
            fmt_rows = exp_df['dt_info'] == fmt
            dt_dmt = DT_FMTS[fmt]['myflightpath_fmt']
            dt_col = DT_FMTS[fmt]['srccol']
            exp_df.loc[fmt_rows, 'date_as_str'] = exp_df.loc[fmt_rows, dt_col].dt.strftime(dt_dmt)

        exp_df['class'].mask(exp_df['airline'] == 'Private flight', 'X', inplace=True), 

        exp_cols = utils.get_keys(col_renames)
        exp_cols = [x for x in exp_cols if x in set(exp_df.columns)]
        exp_df = exp_df[exp_cols].rename(columns=col_renames)

        for time_col in ['departure_time', 'arrival_time']:
            exp_df[time_col] = exp_df[time_col].dt.strftime('%H:%M')

        exp_df['duration'] = exp_df['duration'].apply(lambda x: utils.strfdelta(x, '{H:02}:{M:02}'))
        exp_df['distance'] = exp_df['distance'].apply(lambda x: int(utils.km_to_miles(x)))

        exp_df = exp_df.fillna('')

        exp_df['seat_type'] = exp_df['seat_type'].str.lower()
        exp_df['class'] = exp_df['class'].replace(CLASS_MYFLIGHTPATH_LU)
        exp_df['reason'] = exp_df['reason'].replace(REASON_MYFLIGHTPATH_LU)

        exp_df['is_public'] = "Y"

        self.logger.info(f"exp_df.dtypes:\n{exp_df.dtypes}")
        self.logger.info(f"exp_df:\n{exp_df}")
        self.logger.info(f"exp_df:\n{exp_df.loc[100, :]}")
        
        self.logger.info(f"exp_df:\n{exp_df.loc[exp_df['class'] == 'X', :]}")
        
        exp_df.to_csv(fsave, index=False, encoding='utf-8')
        self.logger.info(f"Finished exporting with format `{exp_format}` to `{fsave}`")


    def export_to(self, exp_format, fsave):
        formats = ['openflights', 'myflightpath']
        if not any(exp_format in f for f in formats):
            msg = f"Unrecognized export format `{exp_format}`; terminating"
            raise ValueError(msg)
        
        self.logger.info(f"Continuing with exp format `{exp_format}`")
        
        if exp_format == 'openflights':
            if fsave is None:
                fsave = 'openflights.csv'
            self._export_to_openflights(fsave)
        elif exp_format == 'myflightpath':
            if fsave is None:
                fsave = 'myflightpath.csv'
            self._export_to_myflightpath(fsave)


    def update_fm_data(self):
        # For converting plane types
        # lu_in_use = fmplanelu.FMPLANELU
        # lu_col = 'airplane_type'
        # fm_text_box_name = 'flugzeug'
        
        # For converting plane types based on registration
        # lu_in_use = fmplanelu.FMREGTYPE
        # lu_col = 'airplane_reg'
        # fm_text_box_name = 'flugzeug'
        
        # For converting airline names
        lu_in_use = fmplanelu.FMAIRLINENAMES
        lu_col = 'airline'
        fm_text_box_name = 'airline'
        
        if not self.logged_in:
            self.logger.info("Need to login to flightmemory.com")
            if self.fm_un is None: self.fm_un = logins.get_fm_un()
            if self.fm_pw is None: self.fm_pw = logins.get_fm_pw()
            self.login()
        
        outer_loop_counter = 0
        
        data_to_lu = self.df[lu_col].unique()
        all_lu_keys = lu_in_use.keys()
        total_loops = self.df[lu_col].isin(all_lu_keys).sum()
        for lu in data_to_lu:
            if lu is None or (lu_in_use.get(lu) is None):
                continue
            rows = self.df[lu_col] == lu
            inner_loop_counter = 0

            urls = self.df.loc[rows, 'detail_url']
            num_urls = len(urls.index)
            new_entry = lu_in_use[lu]

            self.logger.info(f"Replacing `{lu}` with `{new_entry}`")
            for url in urls:
                self.driver.get(url)
                input_type = self.driver.find_element(By.NAME, fm_text_box_name)
                input_type.clear()
                input_type.send_keys(new_entry)
                input_type.submit()
                outer_loop_counter += 1
                inner_loop_counter += 1
                self.logger.info(f"Completed {outer_loop_counter} out of {total_loops} total and replaced {inner_loop_counter} out of {num_urls} for {lu}")
        print("\n")