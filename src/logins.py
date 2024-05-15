import getpass


def get_fm_un():
    return input("Flight Memory username:")


def get_fm_pw():
    return getpass.getpass(prompt="Flight Memory password:")
