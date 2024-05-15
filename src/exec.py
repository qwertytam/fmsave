"""
Exceptions raised by fmsave
"""


class FMSaveError(Exception):
    """
    All other fmsave specific exceptions are all inherited from FMSave
    """


class GeoNamesError(FMSaveError):
    """
    For GeoNames specific errors
    """


class GeoNamesDateReturnError(GeoNamesError):
    """
    For when GeoNames returns data without a 'date' key
    """


class GeoNamesStopError(GeoNamesError):
    """
    For GeoNames errors that require user to fix something and stop running
    """


class GeoNamesHTTPError(GeoNamesStopError):
    """
    For HTTP response code error
    """


class GeoNamesRetryError(GeoNamesStopError):
    """
    For GeoNames request max retry error
    """


class GeoNamesTimeoutError(GeoNamesStopError):
    """
    For GeoNames request timeout error
    """


class GeoNamesConnectionError(GeoNamesStopError):
    """
    For GeoNames urllib connection error
    """


class GeoNamesCreditLimitError(GeoNamesStopError):
    """
    For GeoNames exceeding daily (18), hourly (19) or weekly (20) limit
    """


class GeoNamesUserAuthError(GeoNamesStopError):
    """
    For GeoNames user autentication error
    """
