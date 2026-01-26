"""Module providing login functionality"""

from __future__ import annotations

import getpass


def get_fm_un() -> str:
    """Get flightmemory.com user name"""
    return input("Flight Memory username:")


def get_fm_pw() -> str:
    """Get flightmemory.com password"""
    return getpass.getpass(prompt="Flight Memory password:")
