from modules import dt, td

DT_INFO_YMDT = "YMDT"
DT_INFO_YMDO = "YMDO"
DT_INFO_YMD = "YMD"
DT_INFO_YM = "YM"
DT_INFO_Y = "Y"

DT_FMTS ={
    DT_INFO_YMDT: {
        'fmt': '%Y-%m-%d %H:%M',
        'myflightpath_fmt': '%Y-%m-%d',
        'srccol': 'time_dep',
        },
    DT_INFO_YMDO: {
        'fmt': '%Y-%m-%d',
        'myflightpath_fmt': '%Y-%m-%d',
        'srccol': 'date_as_dt',
        },
    DT_INFO_YMD: {
        'fmt': '%Y-%m-%d',
        'myflightpath_fmt': '%Y-%m-%d',
        'srccol': 'date_as_dt',
        },
    DT_INFO_YM: {
        'fmt': '%Y-%m',
        'myflightpath_fmt': '%Y-%m-%d',
        'srccol': 'date_as_dt',
        },
    DT_INFO_Y: {
        'fmt': '%Y',
        'myflightpath_fmt': '%Y-%m-%d',
        'srccol': 'date_as_dt',
        },
}

KM_TO_MILES = 1 / 1.6094

CLASS_OPENFLIGHTS_LU = {
    "First": "F",
    "Business": "C",
    "EconomyPlus": "P",
    "Economy": "Y", 
}

SEAT_OPENFLIGHTS_LU = {
    "Window": "W",
    "Middle": "M",
    "Aisle": "A",
}

REASON_OPENFLIGHTS_LU = {
    "Business": "B",
    "Personal": "L",
    "Crew": "C",
    "Other": "O",
}

CLASS_MYFLIGHTPATH_LU = {
    'Economy': 'Y',
    'EconomyPlus': 'W',
    'Business': 'J',
    'First': 'F',
    'Premium First': 'R',
    'Private': 'X',
}

REASON_MYFLIGHTPATH_LU = {
    "Business": "business",
    "Personal": "leisure",
    "Crew": "crew",
    "Other": "",
}

STR_TYPE_LU = {
    'str': str,
    'float': float,
    'int': int,
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