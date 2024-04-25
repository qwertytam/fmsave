from pathlib import Path
import re
import logging

mpath = Path(__file__).parent.absolute()

APP_NAME = 'utils'
_module_logger_name = f'{APP_NAME}.{__name__}'
module_logger = logging.getLogger(_module_logger_name)
module_logger.info(f"Module {_module_logger_name} logger initialized")


def check_create_path(dir_path, logger=module_logger):
    """
    Check if path exists, if not, creates path
    
    Checks if `dir_path` contains a file (by looking for a `.` after any
    slashes), resolves the path, then creates path if it does not already exist
    
    Args:
        dir_path: String of path that might include a file
        logger: Logger instance to use
    """
    
    pat_path = r'(\\+|/+)'
    pat_file = r'\.'

    path_splits = re.split(pat_path, dir_path)
    fn_search = re.search(pat_file, ''.join(path_splits[-1:]))
    
    fp = Path(dir_path).resolve()
    
    logger.info(f"resolved path is {fp}")
    
    if fn_search is None:
        # Did not find file in provided path
        logger.info(f"Did not find file name for: {dir_path}")
    else:
        fp = fp.parents[0]
        logger.info(f"Found file name for {dir_path} going with parents")
    
    logger.info(f"Checking and creating path for {fp}")
    Path(fp).mkdir(parents=True, exist_ok=True)


def list_depth(l, n=0):
    """
    Find depth of nested list.
    
    Searches recurseively through given list to determine maximum depth of
    nested lists.
    
    Args:
        l: List to search
        n: Current list depth
    
    Returns:
        List depth as an integer
    """
    if isinstance(l, list) and len(l) > 0:
        return 1 + max(list_depth(e) for e in l)
    else:
        return 0


def get_data_dict_column_names(data_dict, top_level_parent):
    """
    Gets names of keys under the keys `top_level_parent`: `columns`:
    
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
    return [k for k in data_dict[top_level_parent]['columns']]

def get_bottom_lists(l, max_depth = 1):
    """
    Get bottom most list(s) in a nested list
    
    Args:
        l: List to search through
        max_depth: Maximum depth to get list from. 1 is bottom most, 2 is second
        from the bottom, etc.
    
    Returns:
        List of bottom most list(s)
    """
    res = []
    if isinstance(l, list) and list_depth(l) > max_depth:
        for p in range(0, len(l)):
            gbl = get_bottom_lists(l[p])
            if list_depth(gbl) <= max_depth:
                res.append(gbl)
            else:
                res = gbl
    elif isinstance(l, list) and list_depth(l) == max_depth:
        return l
    else:
        return []

    return res


def get_keys_and_parents(d, value):
    """
    Find keys and associated parent hireachy that for the given value.
    
    Searches recurseively through dictionary to find `key: value` pairs that 
    contain the given value. Then returns the parents for each key that contains
    the given value.
    
    Args:
        d: Dictionary to parse
        value: Value to search for
    
    Returns:
        Keys and parents from dictionary for given value as a nested list e.g,
        [['parent1', ['parent2', ['key', 'value']]]] Returns empty list `[]`
        if no matching key: value pairs found.
    """
    res = []
    for k,v in d.items():
        if isinstance(v, dict):
            p = get_keys_and_parents(v, value)
            if p:
                res.append([k] + p)
        elif v == value:
            res.append(k)

    return res


def get_parents_for_keys_with_value(d, value):
    """
    Get parents of keys from dictionary that have the given value
    
    Searches recurseively through dictionary to find `key: value` pairs that 
    contain the given value. Then returns the first level parents for each key.
    
    For example, for `value = 'date'` with:
    `d = {
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
        }`
    
    Result is `['date_str_dep', 'date_str_arr']`
    
    Args:
        d: Dictionary to parse
        value: Value to search for
    
    Returns:
        List of parents that have the matching value. Returns empty list if no
        matching key: value pairs found.
    """
    kps = get_keys_and_parents(d, value)
    if len(kps) > 0:
        kps = get_bottom_lists(kps)
        # filter out empty lists
        kps = [l for l in kps if len(l) > 0]
        res = [p for p, k in kps]
    else:
        res = []
    return res


def get_parents_for_keys_with_all_values(d, values):
    """
    Find key parents that contain all the values in a given dictionary

    Searches recurseively through dictionary to find keys that : value pairs that 
    contain the given value. Then returns the parents.
    
    This is similar to `get_parent_keys_with_value(d, value)` except it looks 
    for multiple values. From the example given in `get_parent_keys_with_value(d, value)`,
    for `values = ['arr', float]` the result is `['lon_arr', 'lat_arr']`.
    
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


def get_parents_with_key_value(d, key, value):
    """
    Find parental hireachy for given keys and values in the dictionary
    
    Searches recurseively through dictionary to find `key: value` pairs that 
    contain the given value. Then returns the parents, keys and values each 
    match.
    
    Args:
        d: Dictionary to parse
        key: Key to search for
        value: Value to search for
    
    Returns:
        List of parents with matching (keys, values) as a tuple e.g.,
        `[ppp1, [pp1, [p1,  (k, v)], [p2,  (k, v)], [p3,  (k, v)]]]`.
    """
    res = []    
    for k,v in d.items():
        if isinstance(v, dict):
            p = get_parents_with_key_value(v, key, value)
            if p:
                res.append([k] + p)
        elif (k == key) and (v == value):
            res.append((k, v))

    return res


def get_parents_with_key_values(d, key, values):
    """
    Find key parents that have the given `key: value` pair; returns result as a 
    dictionary of {parent: value, ...}
    
    Args:
        d: Dictionary to parse
        key: Key to search for
        values: List of values to search for

    Returns:
        Dictionary of parents and values that matched on the key: value pair
        e.g. `{p1: v1, p2: v1, p3: v2}`.
    """
    kvs = [get_parents_with_key_value(d, key, v) for v in values]
    if len(kvs) > 0:
        # unpack the result
        res = get_bottom_lists(kvs, 2)
        
        # now flatten the list of lists
        res = [x for xs in res for x in xs]

        # Now extract parent and value from each [p, (k, v)]
        res = dict([(kv[0], kv[1:][0][1]) for kv in res if len(kv) > 0])
    else:
        res = {}

    return res


def get_parents_list_with_key_values(d, key, values):
    """
    Find key parents that have the given `key: value` pair; returns parents as
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


def filterbyvalue(seq, value):
   for el in seq:
       if el.attribute==value: yield el


def find_keys_containing(d, pat):
    res = {pat: {v: k for k, v in d.items() if pat in k}}
    return res


def replace_item(d, replace_dict):
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


def percent_complete(step, total_steps, bar_width=60, title="", print_perc=True):
    """
    Author is StackOverFlow user WinEunuuchs2Unix
    ref: https://stackoverflow.com/questions/3002085/how-to-print-out-status-bar-and-percentage
    """
    import sys

    # UTF-8 left blocks: 1, 1/8, 1/4, 3/8, 1/2, 5/8, 3/4, 7/8
    utf_8s = ["█", "▏", "▎", "▍", "▌", "▋", "▊", "█"]
    perc = 100 * float(step) / float(total_steps)
    max_ticks = bar_width * 8
    num_ticks = int(round(perc / 100 * max_ticks))
    full_ticks = num_ticks / 8      # Number of full blocks
    part_ticks = num_ticks % 8      # Size of partial block (array index)
    
    disp = bar = ""                 # Blank out variables
    bar += utf_8s[0] * int(full_ticks)  # Add full blocks into Progress Bar
    
    # If part_ticks is zero, then no partial block, else append part char
    if part_ticks > 0:
        bar += utf_8s[part_ticks]
    
    # Pad Progress Bar with fill character
    bar += "▒" * int((max_ticks/8 - float(num_ticks)/8.0))
    
    if len(title) > 0:
        disp = title + ": "         # Optional title to progress display
    
    # Print progress bar in green: https://stackoverflow.com/a/21786287/6929343
    disp += "\x1b[0;32m"            # Color Green
    disp += bar                     # Progress bar to progress display
    disp += "\x1b[0m"               # Color Reset
    if print_perc:
        # If requested, append percentage complete to progress display
        if perc > 100.0:
            perc = 100.0            # Fix "100.04 %" rounding error
        disp += " {:6.2f}".format(perc) + " %"
        disp += f"  {step:,} of {total_steps:,}"
    
    # Output to terminal repetitively over the same line using '\r'.
    sys.stdout.write("\r" + disp)
    sys.stdout.flush()

def print_selection_table(df, display_cols, col_widths):
    # Header row
    msg = f" #:"
    for idx, col in enumerate(display_cols):
            msg += f"  {col:<{col_widths[idx]}}"
    print(msg)

    # Selections
    for idx, r in df.iterrows():
        rprint = r.fillna('')
        msg = ""
        for cidx, col in enumerate(display_cols):
            msg += f"  {str(rprint[col])[slice(0,col_widths[cidx],)]:<{col_widths[cidx]}}"
        print(f"{idx+1:>2}:{msg}")