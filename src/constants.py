from datetime import datetime as dt
from datetime import timedelta as td

DT_INFO_YMDT = "YMDT"
DT_INFO_YMDO = "YMDO"
DT_INFO_YMD = "YMD"
DT_INFO_YM = "YM"
DT_INFO_Y = "Y"

STR_TYPE_LU = {
    'str': str,
    'float': float,
    'dt': dt,
    'td': td,
}

DEFAULT_CHROME_PATH = '/Applications/Chromium.app/Contents/MacOS/Chromium'

CHROME_OPTIONS = [
    '--headless',
    'start-maximized',
    '--disable-blink-features',
    '--disable-blink-features=AutomationControlled',
    ]

MINS_PER_HOUR = 60