"""Geonames API functionality"""

import logging
import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import JSONDecodeError as rJSONDecodeError
from requests.exceptions import ConnectionError as rConnectionError
from urllib3.util.retry import Retry
from urllib3.exceptions import MaxRetryError
from exceptions import (
    GeoNamesError,
    GeoNamesHTTPError,
    GeoNamesRetryError,
    GeoNamesCreditLimitError,
    GeoNamesUserAuthError,
    GeoNamesConnectionError,
    GeoNamesDateReturnError,
)
from constants import URLs, Timeouts, APILimits


APP_NAME = "fmsave"
_module_logger_name = f"{APP_NAME}.{__name__}"
module_logger = logging.getLogger(_module_logger_name)
module_logger.debug("Module %s logger initialized", _module_logger_name)

EMPTY_TZ_DICT = {
    "lat": None,
    "lon": None,
    "date": None,
    "tz_id": None,
    "gmt_offset": None,
}


class GeoNames:
    """sGeonames API functionality"""

    url = URLs.GEONAMES_TIMEZONE

    def __init__(
        self,
        username,
        timeout=Timeouts.API_CALL_DEFAULT,
        user_agent=None,
    ):
        """
        Args:
            username: GeoNames username, required. Sign up here:
                http://www.geonames.org/login
            timeout: timeout for api request
            user_agent user agent for api request
        """
        _class_name = "GeoNames"
        _class_logger_name = f"{_module_logger_name}.{_class_name}"
        self.logger = logging.getLogger(_class_logger_name)
        self.logger.debug("Class %s initialized, _class_logger_name")

        self.timeout = (timeout,)
        self.user_agent = (user_agent,)
        self.username = username

    def _call_geonames(self, url, params, callback, timeout=Timeouts.API_CALL_DEFAULT, maxretries=APILimits.MAX_RETRIES):
        self.logger.debug("Sending request to url: %s\nparams: %s", url, params)
        retry_strategy = Retry(
            total=maxretries,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        http = requests.Session()
        http.mount("https://", adapter)
        http.mount("http://", adapter)

        try:
            response = http.get(url, params=params, timeout=timeout)
        except rConnectionError as err:
            err_msg = f"GeoNames connection error:\n{err}"
            self.logger.error(err_msg)
            raise GeoNamesConnectionError(err_msg) from err
        except MaxRetryError as err:
            err_msg = f"GeoNames max retry error:\n{err}"
            self.logger.error(err_msg)
            raise GeoNamesRetryError(err_msg) from err
        resp_status = response.status_code

        try:
            resp_json = response.json()
            self._raise_for_error(resp_json)
        except rJSONDecodeError as err:
            err_msg = (
                f"GeoNames HTTP error with status code {resp_status}"
                + f"\n{response.text}\nCaused by\n{err}"
            )
            self.logger.error(err_msg)
            raise GeoNamesHTTPError(err_msg) from err

        return callback(resp_json)

    def _raise_for_error(self, body):
        error = body.get("status")
        if error:
            code = error["value"]
            msg = error["message"]
            # http://www.geonames.org/export/webservice-exception.html
            print("\n")
            if msg.startswith("user account not enabled to use"):
                err_msg = (
                    f"GeoNamesUserAuthError: User has insufficient privilieges: {msg}\n"
                )
                self.logger.error(err_msg)
                raise GeoNamesUserAuthError(err_msg)
            if code == 10:
                err_msg = f"GeoNamesUserAuthError: User authentication error: {msg}\n"
                self.logger.error(err_msg)
                raise GeoNamesUserAuthError(err_msg)
            if code == 14:
                err_msg = f"GeoNamesDateReturnError: Invalid date format: {msg}\n"
                self.logger.error(err_msg)
                raise GeoNamesDateReturnError(err_msg)
            if code in (18, 19, 20):
                err_msg = (
                    f"GeoNamesCreditLimitError: GeoNames user quota exceeded: {msg}\n"
                )
                self.logger.error(err_msg)
                raise GeoNamesCreditLimitError(err_msg)
            err_msg = f"GeoNames error: {code} {msg}\n"
            self.logger.error(err_msg)
            raise GeoNamesError(err_msg)

    def _parse_response(self, response):
        self.logger.debug(response)
        lat = float(response.get("lat"))
        lon = float(response.get("lng"))
        tz_id = response.get("timezoneId")
        dates = response.get("dates")

        try:
            date = dates[0].get("date")
            gmt_offset = float(dates[1].get("offsetToGmt"))
        except TypeError as err:
            err_msg = f"Error getting dates; likely error on requests side:\n{err}"
            self.logger.error(err_msg)
            raise GeoNamesDateReturnError(err_msg) from err

        resp_dict = {
            "lat": lat,
            "lon": lon,
            "date": date,
            "tz_id": tz_id,
            "gmt_offset": gmt_offset,
        }

        return resp_dict

    def find_tz(self, lat, lon, date, timeout=Timeouts.API_CALL_DEFAULT, maxretries=APILimits.MAX_RETRIES):
        """
        Find the timezone for a lat, lon and date

        Args:
            lat: latitude in decimal format
            lon: longitude in decimal format
            date: date in 'YYYY-MM-DD' format; optional, uses current system
                date if not given
            timeout: time, in seconds, to wait for GeoNames to respond
            maxretries: maximum retries to get request from GeoNames

        Return:
            Dictionary with 'lat', 'lon', 'date', 'tz_id', and 'gmt_offset'
        """
        params = {
            "lat": lat,
            "lng": lon,
            "date": date,
            "username": self.username,
        }
        return self._call_geonames(
            self.url, params, self._parse_response, timeout, maxretries
        )
