"""Module to hold default configuation settings."""

from constants import ChromeDefaults

# Selenium chrome web driver
DEFAULT_CHROME_PATH = ChromeDefaults.DEFAULT_PATH

CHROME_OPTIONS = [
    "--headless",
    "start-maximized",
    "--disable-blink-features",
    "--disable-blink-features=AutomationControlled",
]
