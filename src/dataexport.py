import data
import utils
from constants import STR_TYPE_LU
import pandas as pd
from thefuzz import process

def get_openflights_data(data_set, logger, exp_format='openflights', supplemental=False):
    """
    Get openflights data set
    
    Args:
        data_set: openflights data set to get
        logger: Python logger to use
        exp_format: Export format i.e. 'openflights'
        supplemental: Wether to get '_supplemental.csv' data set
    
    Returns:
        openflights data set as pandas data frame
    """
    data_dict = data.get_yaml(exp_format, data_set, logger)
    col_names = utils.get_data_dict_column_names(data_dict, data_set)
    
    col_types = utils.get_parents_with_key_values(
        data_dict,
        key='type',
        values=['float', 'str'])
    col_types = utils.replace_item(col_types, STR_TYPE_LU)
    
    of_data = data.get_openflights_data(data_set, names=col_names, dtype=col_types, supplemental=supplemental)
    return of_data


def get_openflights_airport_data(logger):
    """
    Get openflights airport data set
    
    Args:
        logger: Python logger to use
    
    Returns:
        openflights airport data set as pandas data frame
    """
    data_set = 'airports'
    base = get_openflights_data(data_set, logger)
    supplemental = get_openflights_data(data_set, logger, supplemental=True)
    
    return pd.concat([base, supplemental])
    
    
def fuzzy_match_of_airports(df, airport_data, check_col, data_col, find_col, logger):
    """
    Fuzzy matching user airports to openflights airport data set
    
    Args:
        df: user data to find matches for
        airport_data: openflights airport data set
        check_col: column name in 'df' to update with match
        data_col: column name in 'airport_data' to search for match
        find_col: column name in 'df` to search for in `airport_data'
        logger: Python logger to use
    
    Returns:
        df with updated fuzzy matches
    """
    row_filter = df[check_col].isna()
    mismatch_rows = df.loc[row_filter, :]
    logger.debug(f"There are {len(mismatch_rows)} mismatches")
    
    display_cols = [
        'IATA',
        'ICAO',
        'Airport_Name',
        'Country',
        'City',
        ]

    col_widths = [
        4,
        7,
        40,
        11,
        25,
    ]

    for mmidx, mm in mismatch_rows.iterrows():
        find_str = mm[find_col]
        sel_row = data.select_fuzzy_match(
            airport_data,
            find_str,
            'Airport_Name',
            display_cols,
            col_widths,
            logger=logger,)
        
        if sel_row is None:
            continue
        else:
            df.loc[mmidx, check_col] = sel_row[data_col].values[0]

    return df


def match_openflights_airports(df, logger):
    """
    Match openflights airport data set to user airport data
    
    Args:
        df: user data to find match
        logger: Python logger to use
    
    Returns:
        df with updated openflight data match
    """
    of_airports = get_openflights_airport_data(logger)
    
    new_col = 'From_OID'
    of_airports[new_col] = of_airports['ID']
    inc_cols = ['ICAO', new_col]
    df = df.join(
        of_airports[inc_cols].set_index('ICAO'),
        how='left',
        on='icao_dep',
        lsuffix='_org',
        rsuffix='_dep')

    df = fuzzy_match_of_airports(df, of_airports, new_col, new_col, 'name_dep', logger)

    of_airports = of_airports.rename(columns={new_col : 'To_OID'})
    new_col = 'To_OID'
    inc_cols = ['ICAO', new_col]
    df = df.join(
        of_airports[inc_cols].set_index('ICAO'),
        how='left',
        on='icao_arr',
        lsuffix='_dep',
        rsuffix='_arr')

    df = fuzzy_match_of_airports(df, of_airports, new_col, new_col, 'name_arr', logger)
    
    return df


def _get_list_tofuzz_on(df, to_find, to_find_col, to_match_col):
    return df.loc[df[to_find_col] == to_find, to_match_col].values[0]


def _fuzzy_match_openflights(df, to_find_col, to_match_col, limit=1, threshold=90):
    matches = df[to_find_col].apply(
        lambda to_find: process.extract(
            to_find,
            _get_list_tofuzz_on(df, to_find, to_find_col, to_match_col),
            limit=limit))

    df[to_match_col] = matches.apply(
        lambda x: ', '.join(i[0] for i in x if i[1] >= threshold))
    return df


def fuzzy_match_of_airlines_iata_name(df, filter_col, df_name_col, df_iata_col,
                                      airline_data, data_name_col, data_iata_col,
                                      inc_cols):
    """
    Fuzzy matching user airlines to openflights airline data set using iata code
    and airline name
    
    Args:
        df: user data to find matches for
        filter_col: column name in df to filter on 'isna()' to find matches for
        df_name_col: column name in df that has airline name
        df_iata_col: column name in df that has airline iata code
        airline_data: openflights airline data set
        data_name_col: column name in airline_data that has airline name
        data_iata_col: column name in airline_data that has airline iata code
        inc_cols: column names to include from airline_data
    
    Returns:
        df with updated fuzzy matches
    """

    missing_mask = df[filter_col].isna() & (df[df_iata_col].str.len() > 0)
    iatas_to_match = set(df.loc[missing_mask, df_iata_col].tolist())

    data_to_match = airline_data.loc[airline_data[data_iata_col].isin(iatas_to_match), [data_iata_col, data_name_col]]
    data_to_match = data_to_match.groupby(data_iata_col)[data_name_col].apply(list).to_frame(name=data_name_col)
    
    data_to_match = data_to_match.merge(
                df[[df_iata_col, df_name_col]],
                how='left',
                left_on=data_iata_col,
                right_on=df_iata_col)

    data_to_match = _fuzzy_match_openflights(data_to_match, df_name_col, data_name_col)
    
    inc_cols = [data_name_col, filter_col]
    data_to_match = data_to_match.join(
        airline_data[inc_cols].set_index(data_name_col),
        how='left',
        on=data_name_col,)
    
    inc_cols = [df_name_col, filter_col]
    df = df.join(
        data_to_match[inc_cols].set_index(df_name_col),
        how='left',
        on=df_name_col,
        rsuffix='_match')
    
    df.loc[missing_mask, filter_col] = df.loc[missing_mask, filter_col + '_match']
    df = df.drop(columns=[filter_col + '_match'])

    return df


def match_openflights_airlines(df, logger):
    """
    Match openflights airline data set to user airline data
    
    Args:
        df: user data to find match
        logger: Python logger to use
    
    Returns:
        df with updated openflight data match
    """
    # Get openflights airline data
    data_set = 'airlines'
    airline_data = get_openflights_data(data_set, logger)
    airline_data = airline_data.fillna('')
    
    # Get flight info that we need to match
    df_iata_col = 'iata_airline'
    df_name_col = 'airline'
    df_match = df[[df_iata_col, df_name_col]].fillna('').drop_duplicates().reset_index(drop=True)

    # Adding new col to include as part of join operation
    col_name_sep = '_'
    data_id_col = 'ID'
    new_id_col = 'Airline' + col_name_sep + 'OID'
    airline_data[new_id_col] = airline_data[data_id_col]

    # First going to join on IATA and Name
    data_iata_col = 'IATA'
    data_name_col = 'Name'
    new_match_col = data_iata_col + col_name_sep + data_name_col

    # Create new key of 'iata_name' in df and data...
    df_match[new_match_col] = df_match[df_iata_col] + col_name_sep + df_match[df_name_col]
    airline_data[new_match_col] = airline_data[data_iata_col] + col_name_sep + airline_data[data_name_col]

    # ...then join on the new key
    inc_cols = [new_match_col, new_id_col]
    df_match = df_match.join(
        airline_data[inc_cols].set_index(new_match_col),
        how='left',
        on=new_match_col,)

    # Now going to fuzzy match on name, where name is associated with iata
    df_match = fuzzy_match_of_airlines_iata_name(
        df_match, new_id_col, df_name_col, df_iata_col,
        airline_data, data_name_col, data_iata_col,
        inc_cols)

    # Now fuzzy match on name alone
    names_to_match = df_match.loc[df_match[new_id_col].isna(), 'airline'].to_frame()
    names_to_match = names_to_match.loc[names_to_match['airline'].str.len() > 0, 'airline'].to_frame()

    limit = 1
    threshold = 90
    sequences = airline_data[data_name_col].unique().tolist()
    matches = names_to_match['airline'].apply(lambda x: process.extract(x, sequences, limit=limit))
    names_to_match[data_name_col] = matches.apply(lambda x: ', '.join(i[0] for i in x if i[1] >= threshold))
        
    inc_cols = [data_name_col, new_id_col]
    names_to_match = names_to_match.join(
        airline_data[inc_cols].set_index(data_name_col),
        how='left',
        on=data_name_col,)

    for i, r in names_to_match.iterrows():
        df_match.loc[df_match[df_name_col] == r[df_name_col], new_id_col] = r[new_id_col]

    df_match = df_match.drop_duplicates(subset=[df_name_col])    
    inc_cols = [df_name_col, new_id_col]

    df = df.join(
        df_match[inc_cols].set_index(df_name_col),
        how='left',
        on=df_name_col,)

    return df