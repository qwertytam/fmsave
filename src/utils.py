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


def find_keys(d, value):
    """
    Find keys and associated parents that for the given value.
    
    Searches recurseively through dictionary to find `key: value` pairs that 
    contain the given value. Then returns the parents for each key that contains
    the given value.
    
    Args:
        d       dictionary to parse
        value   value to search for
    """
    res = []
    for k,v in d.items():
        if isinstance(v, dict):
            p = find_keys(v, value)
            if p:
                res.append([k] + p)
        elif v == value:
            res.append(k)

    return res


def get_cols_with_value(d, value):
    """
    Get columns that have a `key: value`
    
    Searches recurseively through dictionary to find `key: value` pairs that 
    contain the given value. Then returns the parent key, or `column` in this
    context.
    
    Args:
        d       dictionary to parse
        value   value to search for
    """
    keys = find_keys(d, value)[0][1][1:]
    res = [col for col, k in keys]
    return res


def get_cols_with_values(d, values):
    """
        Find columns that contain all the values in a given dictionary
        
        Args:
            d       dictionary to parse
            values  list of values to search for
    """
    all_cols = [get_cols_with_value(d, v) for v in values]
    sets = [set(c) for c in all_cols]
    return set.intersection(*sets)