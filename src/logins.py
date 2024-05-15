"""Module providing login functionality"""

import getpass


def get_fm_un():
    """Get flightmemory.com user name"""
    return input("Flight Memory username:")


def get_fm_pw():
    """Get flightmemory.com password"""
    return getpass.getpass(prompt="Flight Memory password:")
