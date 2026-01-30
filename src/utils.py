"""Utility helper functions"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
import re
from string import Formatter
from datetime import datetime as dt
from datetime import timedelta
from typing import Any
import pandas as pd
from constants import DistanceConversions

mpath = Path(__file__).parent.absolute()

APP_NAME = "utils"
_MODULE_LOGGER_NAME = f"{APP_NAME}.{__name__}"
module_logger = logging.getLogger(_MODULE_LOGGER_NAME)
module_logger.debug("Module %s logger initialized", _MODULE_LOGGER_NAME)


def check_create_path(
    dir_path: str | Path, logger: logging.Logger = module_logger
) -> None:
    """
    Check if path exists, if not, creates path

    Checks if 'dir_path' contains a file (by looking for a '.' after any
    slashes), resolves the path, then creates path if it does not already exist

    Args:
        dir_path: String of path that might include a file
        logger: Logger instance to use
    """

    pat_path = r"(\\+|/+)"
    pat_file = r"\."

    path_splits = re.split(pat_path, str(dir_path))
    fn_search = re.search(pat_file, "".join(path_splits[-1:]))

    fp = Path(dir_path).resolve()

    logger.info(f"resolved path is {fp}")

    if fn_search is None:
        # Did not find file in provided path
        logger.info("Did not find file name for: %s", dir_path)
    else:
        fp = fp.parents[0]
        logger.info("Found file name for %s going with parents", dir_path)

    logger.info("Checking and creating path for %s", fp)
    Path(fp).mkdir(parents=True, exist_ok=True)


def list_depth(lst: list[Any]) -> int:
    """
    Find depth of nested list.

    Searches recurseively through given list to determine maximum depth of
    nested lists.

    Args:
        lst: List to search

    Returns:
        List depth as an integer
    """
    if isinstance(lst, list) and len(lst) > 0:
        return 1 + max(list_depth(e) for e in lst)
    else:
        return 0


def get_data_dict_column_names(
    data_dict: dict[Any, Any], top_level_parent: str
) -> list[Any]:
    """
    Gets names of keys under the keys 'top_level_parent': 'columns':

    For example:
    ```
    airports:
        columns:
            name:
                detail1:
                detail2:
            id:
                detail1:
                detail2:
    ```
    It will return ['name', 'id']

    Args:
        data_dict: Data dictionary to get column names from
        top_level_parent: Name of top level parent

    Returns:
        List of column names
    """
    return [k for k in data_dict[top_level_parent]["columns"]]


def get_bottom_lists(lst: list[Any], max_depth: int = 1) -> list[Any]:
    """
    Get bottom most list(s) in a nested list

    Args:
        lst: List to search through
        max_depth: Maximum depth to get list from. 1 is bottom most, 2 is second
        from the bottom, etc.

    Returns:
        List of bottom most list(s)
    """
    res = []
    if isinstance(lst, list) and list_depth(lst) > max_depth:
        for i, _ in enumerate(lst):
            gbl = get_bottom_lists(lst[i])
            if list_depth(gbl) <= max_depth:
                res.append(gbl)
            else:
                res = gbl
    elif isinstance(lst, list) and list_depth(lst) == max_depth:
        return lst
    else:
        return []

    return res


def get_keys_and_parents(d: dict[str, Any], value: Any) -> list[Any]:
    """
    Find keys and associated parent hireachy that for the given value.

    Searches recurseively through dictionary to find 'key: value' pairs that
    contain the given value. Then returns the parents for each key that contains
    the given value.

    Args:
        d: Dictionary to parse
        value: Value to search for

    Returns:
        Keys and parents from dictionary for given value as a nested list e.g,
        [['parent1', ['parent2', ['key', 'value']]]] Returns empty list '[]'
        if no matching key: value pairs found.
    """
    res = []
    for k, v in d.items():
        if isinstance(v, dict):
            p = get_keys_and_parents(v, value)
            if p:
                res.append([k] + p)
        elif v == value:
            res.append([k])

    return res


def _extract_parents_from_nested(lst: list[Any], parents: list[str] | None = None) -> list[str]:
    """
    Extract parent keys from nested list structure returned by get_keys_and_parents.
    
    For a structure like ['airports', ['columns', ['time_dep', ['data']], ['time_arr', ['data']]]]
    this returns ['time_dep', 'time_arr'] - the keys whose children contain the searched value.
    
    Args:
        lst: Nested list from get_keys_and_parents
        parents: Accumulated parent keys (used in recursion)
        
    Returns:
        List of parent keys that contain the searched value
    """
    if parents is None:
        parents = []
    
    result = []
    
    if not isinstance(lst, list) or len(lst) == 0:
        return result
    
    # Check if this is a leaf node [key] where key is a string
    if len(lst) == 1 and isinstance(lst[0], str):
        # This is a terminal [key] - the parent we want is in `parents`
        if parents:
            result.append(parents[-1])
        return result
    
    # Check if first element is a string (a key) followed by nested lists
    if isinstance(lst[0], str):
        key = lst[0]
        new_parents = parents + [key]
        # Process remaining elements
        for item in lst[1:]:
            if isinstance(item, list):
                result.extend(_extract_parents_from_nested(item, new_parents))
    else:
        # It's a list of lists - process each
        for item in lst:
            if isinstance(item, list):
                result.extend(_extract_parents_from_nested(item, parents))
    
    return result


def get_parents_for_keys_with_value(d: dict[str, Any], value: Any) -> list[Any]:
    """
    Get parents of keys from dictionary that have the given value

    Searches recurseively through dictionary to find 'key: value' pairs that
    contain the given value. Then returns the first level parents for each key.

    For example, for 'value = 'date'' with:
    ```
    d = {
        'date_str_dep': {
            'data': 'date',
            'format': 'yyyy-mm-dd',
            'leg': 'dep',
            },
        'lat_dep': {
            'data': 'lat',
            'format': float,
            'leg': 'dep',
            },
        'lon_dep': {
            'data': 'lon',
            'format': float,
            'leg': 'dep',
            },
        'date_str_arr': {
            'data': 'date',
            'format': 'yyyy-mm-dd',
            'leg': 'arr',
            },
        'lat_arr': {
            'data': 'lat',
            'format': float,
            'leg': 'arr',
            },
        'lon_arr': {
            'data': 'lon',
            'format': float,
            'leg': 'arr',
            },
        }
        ```

    Result is '['date_str_dep', 'date_str_arr']'

    Args:
        d: Dictionary to parse
        value: Value to search for

    Returns:
        List of parents that have the matching value. Returns empty list if no
        matching key: value pairs found.
    """
    kps = get_keys_and_parents(d, value)
    if len(kps) > 0:
        res = _extract_parents_from_nested(kps)
    else:
        res = []
    return res


def get_parents_for_keys_with_all_values(
    d: dict[str, Any], values: list[Any]
) -> list[Any]:
    """
    Find key parents that contain all the values in a given dictionary

    Searches recurseively through dictionary to find keys that : value pairs that
    contain the given value. Then returns the parents.

    This is similar to 'get_parent_keys_with_value(d, value)' except it looks
    for multiple values. From the example given in 'get_parent_keys_with_value(d, value)',
    for 'values = ['arr', float]' the result is '['lon_arr', 'lat_arr']'.

    Note the result is the intersection (i.e. boolean AND) of the values, not
    the union (i.e. boolean OR).

    Args:
        d: Dictionary to parse
        values: List of values to search for

    Returns:
        List of parents that have the matching values. Returns empty list if no
        matching key: value pairs found.
    """
    all_cols = [get_parents_for_keys_with_value(d, v) for v in values]
    sets = [set(c) for c in all_cols]
    return list(set.intersection(*sets))


def get_parents_with_key_value(
    d: dict[str, Any], key: str, value: Any, regex: bool = False
) -> list[Any]:
    """
    Find parental hireachy for given keys and values in the dictionary

    Searches recurseively through dictionary to find 'key: value' pairs that
    contain the given value. Then returns the parents, keys and values each
    match.

    Args:
        d: Dictionary to parse
        key: Key to search for
        value: Value to search for
        regex: If True, then key and value are regex patterns; else they are strings

    Returns:
        List of parents with matching (keys, values) as a tuple e.g.,
        '[ppp1, [pp1, [p1,  (k, v)], [p2,  (k, v)], [p3,  (k, v)]]]'.
    """
    res: list[Any] = []
    for k, v in d.items():
        if isinstance(v, dict):
            p = get_parents_with_key_value(v, key, value, regex)
            if p:
                res.append([k] + p)
        else:
            if regex:
                k_match = re.compile(key).match(str(k)) is not None
                v_match = re.compile(value).match(str(v)) is not None
                match = k_match and v_match

            else:
                match = (k == key) and (v == value)

            if match:
                res.append((k, v))

    return res


def get_parents_with_key_values(
    d: dict[str, Any], key: str, values: list[Any], regex: bool = False
) -> dict[str, Any]:
    """
    Find key parents that have the given 'key: value' pair; returns result as a
    dictionary of {parent: value, ...}

    Args:
        d: Dictionary to parse
        key: Key to search for
        values: List of values to search for

    Returns:
        Dictionary of parents and values that matched on the key: value pair
        e.g. '{p1: v1, p2: v1, p3: v2}'.
    """
    kvs = [get_parents_with_key_value(d, key, v, regex) for v in values]
    if len(kvs) > 0:
        # unpack the result
        unpacked = get_bottom_lists(kvs, 2)

        # now flatten the list of lists
        flattened = [x for xs in unpacked for x in xs]

        # Now extract parent and value from each [p, (k, v)]
        return {kv[0]: kv[1:][0][1] for kv in flattened if len(kv) > 0}
    else:
        return {}


def get_parents_list_with_key_values(
    d: dict[str, Any], key: str, values: list[Any]
) -> list[str]:
    """
    Find key parents that have the given 'key: value' pair; returns parents as
    a list

    Args:
        d: Dictionary to parse
        key: Key to search for
        values: List of values to search for

    Returns:
        List of parents with the key: value pair
    """
    res = get_parents_with_key_values(d, key, values)
    return [k for k, v in res.items()]


def filterbyvalue(seq: Any, value: Any) -> Any:
    """
    Filter sequence by value
    """
    for el in seq:
        if el.attribute == value:
            yield el


def find_keys_containing(d: dict[str, Any], pat: str) -> dict[str, dict[Any, str]]:
    """
    Find keys in dictionary containing given pattern

    Args:
        d: Dictionary to search through
        pat: Pattern to find

    Returns:
        Dictionary with keys that contain the pattern
    """
    res = {pat: {v: k for k, v in d.items() if pat in k}}
    return res


def replace_item(d: dict[str, Any], replace_dict: dict[Any, Any]) -> dict[str, Any]:
    """
    Replace values in dictionary d based on replacement lookup dictionary.

    Example:
        d = {'fred': 'smith', 'jane': 'smith', 'harry': 'tom'}
        replace_dict = {'smith': 'doe', 'tom': 'bloes'}
        result = {'fred': 'doe', 'jane': 'doe', 'harry': 'bloes'}

    Args:
        d: Dictionary to replace values in
        replace_dict: Lookup dictionary where format is {old: new}

    Returns:
        Updated dictionary with replacements
    """
    for k, v in d.items():
        if isinstance(v, dict):
            d[k] = replace_item(v, replace_dict)
        elif v in replace_dict:
            d[k] = replace_dict[v]
    return d


def percent_complete(
    step: int,
    total_steps: int,
    bar_width: int = 60,
    title: str = "",
    print_perc: bool = True,
) -> None:
    """
    Author is StackOverFlow user WinEunuuchs2Unix
    ref: https://stackoverflow.com/questions/3002085/how-to-print-out-status-bar-and-percentage
    """
    # UTF-8 left blocks: 1, 1/8, 1/4, 3/8, 1/2, 5/8, 3/4, 7/8
    utf_8s = ["█", "▏", "▎", "▍", "▌", "▋", "▊", "█"]
    perc = 100 * float(step) / float(total_steps)
    max_ticks = bar_width * 8
    num_ticks = int(round(perc / 100 * max_ticks))
    full_ticks = num_ticks / 8  # Number of full blocks
    part_ticks = num_ticks % 8  # Size of partial block (array index)

    disp = disp_bar = ""  # Blank out variables
    disp_bar += utf_8s[0] * int(full_ticks)  # Add full blocks into Progress Bar

    # If part_ticks is zero, then no partial block, else append part char
    if part_ticks > 0:
        disp_bar += utf_8s[part_ticks]

    # Pad Progress Bar with fill character
    disp_bar += "▒" * int((max_ticks / 8 - float(num_ticks) / 8.0))

    if len(title) > 0:
        disp = title + ": "  # Optional title to progress display

    # Print progress bar in green: https://stackoverflow.com/a/21786287/6929343
    disp += "\x1b[0;32m"  # Color Green
    disp += disp_bar  # Progress bar to progress display
    disp += "\x1b[0m"  # Color Reset
    if print_perc:
        # If requested, append percentage complete to progress display
        if perc > 100.0:
            perc = 100.0  # Fix "100.04 %" rounding error
        disp += f" {perc:6.2f} %"
        disp += f"  {step:,} of {total_steps:,}"

    # Output to terminal repetitively over the same line using '\r'.
    sys.stdout.write("\r" + disp)
    sys.stdout.flush()


def print_selection_table(
    df: pd.DataFrame, display_cols: list[str], col_widths: list[int]
) -> None:
    """
    Print columns in dataframe using given widths

    Args:
        df: Dataframe to print columns from
        display_cols: Columns to print from df
        col_widths: Character widths to use for printed columns
    """
    # Header row
    msg = " #:"
    for idx, col in enumerate(display_cols):
        msg += f"  {col:<{col_widths[idx]}}"
    print(msg)

    # Selections
    ridx = 0
    for _, r in df.iterrows():
        ridx += 1
        rprint = r.fillna("")
        msg = ""
        for cidx, col in enumerate(display_cols):
            msg += (
                f"  {str(rprint[col])[slice(0,col_widths[cidx],)]:<{col_widths[cidx]}}"
            )
        print(f"{ridx:>2}:{msg}")


def swap_keys_values(d: dict[Any, Any]) -> dict[Any, Any]:
    """
    Swaps keys with values in given dictionary

    Args:
        d: Dictionary to swap keys and values in

    Returns:
        Dictionary with swaped keys and values
    """
    return dict((v, k) for k, v in d.items())


def get_keys(d: dict[Any, Any]) -> list[str]:
    """
    Get all keys from given dictionary

    Args:
        d: Dictionary to get keys from

    Returns:
        List of all keys from d
    """
    return [k for k, v in d.items()]


def strfdelta(
    tdelta: timedelta | int | float,
    fmt: str = "{D:02}d {H:02}h {M:02}m {S:02}s",
    inputtype: str = "timedelta",
) -> str:
    """Convert a datetime.timedelta object or a regular number to a custom-
    formatted string, just like the stftime() method does for datetime.datetime
    objects.

    The fmt argument allows custom formatting to be specified.  Fields can
    include seconds, minutes, hours, days, and weeks.  Each field is optional.

    Some examples:
        '{D:02}d {H:02}h {M:02}m {S:02}s' --> '05d 08h 04m 02s' (default)
        '{W}w {D}d {H}:{M:02}:{S:02}'     --> '4w 5d 8:04:02'
        '{D:2}d {H:2}:{M:02}:{S:02}'      --> ' 5d  8:04:02'
        '{H}h {S}s'                       --> '72h 800s'

    The inputtype argument allows tdelta to be a regular number instead of the
    default, which is a datetime.timedelta object.  Valid inputtype strings:
        's', 'seconds',
        'm', 'minutes',
        'h', 'hours',
        'd', 'days',
        'w', 'weeks'

    From: https://stackoverflow.com/questions/538666/format-timedelta-to-string#538721
    Full credit to stackoverflow author MarredCheese
    """

    # Convert tdelta to integer seconds.
    if inputtype == "timedelta":
        assert isinstance(tdelta, timedelta)
        remainder = int(tdelta.total_seconds())
    else:
        assert isinstance(tdelta, (int, float))
        if inputtype in ["s", "seconds"]:
            remainder = int(tdelta)
        elif inputtype in ["m", "minutes"]:
            remainder = int(tdelta) * 60
        elif inputtype in ["h", "hours"]:
            remainder = int(tdelta) * 3600
        elif inputtype in ["d", "days"]:
            remainder = int(tdelta) * 86400
        elif inputtype in ["w", "weeks"]:
            remainder = int(tdelta) * 604800
        else:
            remainder = int(tdelta)

    f = Formatter()
    desired_fields = [field_tuple[1] for field_tuple in f.parse(fmt)]
    possible_fields = ("W", "D", "H", "M", "S")
    constants = {"W": 604800, "D": 86400, "H": 3600, "M": 60, "S": 1}
    values = {}
    for field in possible_fields:
        if field in desired_fields and field in constants:
            values[field], remainder = divmod(remainder, constants[field])
    return f.format(fmt, **values)


def km_to_miles(km: float) -> float:
    """
    Convert kilometres to statute miles

    Args:
        km: Kilometres to convert

    Returns:
        km converted to miles
    """
    return km * DistanceConversions.KM_TO_MILES.value


def date_to_dt(ddmmyyyy: str) -> dt:
    """
    Convert string to datetime

    Args:
        ddmmyyyy: Date as string in format 'dd-mm-yyyy'

    Returns:
        ddmmyyyy as datetime
    """
    return dt.strptime(ddmmyyyy, "%d-%m-%Y")
