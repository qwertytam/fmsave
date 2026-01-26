"""Module for loading configuration from environment variables and config files."""

import os
from pathlib import Path
import yaml

DEFAULT_CHROME_PATH = "/Applications/Chromium.app/Contents/MacOS/Chromium"
CONFIG_FILENAME = ".fmsaverc"


def _find_config_file():
    """
    Find configuration file in order of precedence:
    1. Current directory
    2. User's home directory
    
    Returns:
        Path to config file if found, None otherwise
    """
    # Check current directory first
    cwd_config = Path.cwd() / CONFIG_FILENAME
    if cwd_config.exists():
        return cwd_config
    
    # Check home directory
    home_config = Path.home() / CONFIG_FILENAME
    if home_config.exists():
        return home_config
    
    return None


def _load_config_file():
    """
    Load configuration from file.
    
    Returns:
        Dictionary with configuration values, empty dict if no file found
    """
    config_path = _find_config_file()
    if config_path is None:
        return {}
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config if config else {}
    except yaml.YAMLError as e:
        print(f"Warning: Error parsing config file {config_path}: {e}")
        return {}
    except Exception as e:
        print(f"Warning: Error reading config file {config_path}: {e}")
        return {}


def get_config():
    """
    Get configuration from environment variables and config file.
    
    Priority (highest to lowest):
    1. Environment variables
    2. Config file (.fmsaverc)
    3. Default values
    
    Returns:
        Dictionary with configuration values
    """
    # Load from config file first
    config = _load_config_file()
    
    # Environment variables override config file
    env_mappings = {
        "FMSAVE_GN_USERNAME": "geonames_username",
        "FMSAVE_FM_USERNAME": "flightmemory_username",
        "FMSAVE_CHROME_PATH": "chrome_path",
        "FMSAVE_DATA_PATH": "default_data_path",
    }
    
    for env_var, config_key in env_mappings.items():
        env_value = os.environ.get(env_var)
        if env_value:
            config[config_key] = env_value
    
    return config


def get_geonames_username(cli_value=None):
    """
    Get GeoNames username from CLI, environment, or config file.
    
    Args:
        cli_value: Value provided via command line argument
        
    Returns:
        GeoNames username or None if not configured
    """
    if cli_value:
        return cli_value
    
    config = get_config()
    return config.get("geonames_username")


def get_flightmemory_username(cli_value=None):
    """
    Get FlightMemory username from CLI, environment, or config file.
    
    Args:
        cli_value: Value provided via command line argument
        
    Returns:
        FlightMemory username or None if not configured
    """
    if cli_value:
        return cli_value
    
    config = get_config()
    return config.get("flightmemory_username")


def get_chrome_path(cli_value=None):
    """
    Get Chrome/Chromium path from CLI, environment, or config file.
    
    Args:
        cli_value: Value provided via command line argument
        
    Returns:
        Path to Chrome executable
    """
    if cli_value:
        return cli_value
    
    config = get_config()
    return config.get("chrome_path", DEFAULT_CHROME_PATH)


def get_default_data_path():
    """
    Get default data path from environment or config file.
    
    Returns:
        Default data path or None if not configured
    """
    config = get_config()
    path = config.get("default_data_path")
    if path:
        return str(Path(path).expanduser())
    return None
