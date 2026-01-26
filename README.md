# fmsave

Download, validate, and export flight data from [flightmemory.com](https://www.flightmemory.com) for use with other flight tracking websites.

## Prerequisites

### 1. Python Environment

- Python 3.12+
- Poetry for dependency management

```bash
# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

### 2. Chrome/Chromium Browser

Selenium requires a Chrome or Chromium browser for downloading HTML pages. The default path is:

``` bash
/Applications/Chromium.app/Contents/MacOS/Chromium
```

You can override this by passing the `<chrome_path>` argument to the `dlhtml` command.

### 3. GeoNames Account

You need a free [GeoNames](http://www.geonames.org/login) account for timezone lookups.

- Sign up at: <http://www.geonames.org/login>
- Enable the account for web services in your account settings
- Note: Free tier has a limit of 1,000 API calls per hour

### 4. FlightMemory Account

You need your flightmemory.com username and password. The password is prompted securely at runtime.

---

## Quick Start Workflow

### Step 1: Download HTML from FlightMemory

```bash
cd src
python fmsave.py dlhtml <fm_username> <save_path>
```

**Example:**

```bash
python fmsave.py dlhtml myusername ~/flightdata/html/
```

This downloads all your flight pages from flightmemory.com as HTML files. You'll be prompted for your password.

### Step 2: Convert HTML to CSV

```bash
python fmsave.py tocsv <geonames_username> <html_path> <output.csv>
```

**Example:**

```bash
python fmsave.py tocsv mygeouser ~/flightdata/html/ ~/flightdata/flights.csv
```

This parses the HTML files and creates a CSV with flight data including lat/lon and timezones.

### Step 3: Update Timezone Information (if needed)

If you hit the GeoNames API limit during Step 2, run this after waiting:

```bash
python fmsave.py uptz <geonames_username> <flights.csv>
```

**Example:**

```bash
python fmsave.py uptz mygeouser ~/flightdata/flights.csv
```

### Step 4: Export to Other Formats

```bash
python fmsave.py export <format> <flights.csv> <output.csv>
```

**Example:**

```bash
python fmsave.py export openflights ~/flightdata/flights.csv ~/flightdata/openflights.csv
python fmsave.py export myflightpath ~/flightdata/flights.csv ~/flightdata/myflightpath.csv
```

---

## All Commands

| Command | Description |
| --------- | ------------- |
| `dlhtml` | Download HTML pages from flightmemory.com |
| `tocsv` | Convert HTML pages to CSV file |
| `upcsv` | Update existing CSV file with new HTML data |
| `uptz` | Update timezone information in CSV file |
| `validate` | Validate distances and flight times |
| `upair` | Update airport information data file |
| `upof` | Update OpenFlights data files |
| `upwiki` | Update Wikipedia aircraft type codes |
| `export` | Export data to other website formats |

---

## Detailed Command Usage

### `dlhtml` - Download HTML Pages

Downloads flight pages from flightmemory.com and saves them as HTML files.

**Usage:**

```bash
python fmsave.py dlhtml <fm_username> <save_path> [<chrome_path> --max-pages=MAX_PAGES]
```

**Arguments:**

- `<fm_username>`: Your flightmemory.com username
- `<save_path>`: Directory to save HTML files
- `<chrome_path>`: (Optional) Path to Chrome/Chromium executable
- `--max-pages=N`: (Optional) Maximum number of pages to download

**Examples:**

```bash
# Download all flight pages
python fmsave.py dlhtml johndoe ~/flights/html/

# Download only first 10 pages
python fmsave.py dlhtml johndoe ~/flights/html/ --max-pages=10

# Use custom Chrome path
python fmsave.py dlhtml johndoe ~/flights/html/ /usr/bin/chromium
```

---

### `tocsv` - Convert HTML to CSV

Parses HTML flight pages and creates a CSV file with flight data, including coordinates and timezones.

**Usage:**

```bash
python fmsave.py tocsv <geonames_username> <html_path> <output.csv>
```

**Arguments:**

- `<geonames_username>`: Your GeoNames username
- `<html_path>`: Directory containing HTML files
- `<output.csv>`: Path and filename for output CSV

**Example:**

```bash
python fmsave.py tocsv mygeouser ~/flights/html/ ~/flights/data.csv
```

**Note:** This command calls the GeoNames API for each airport. If you have many flights, you may hit the 1,000 calls/hour limit.

---

### `upcsv` - Update Existing CSV

Updates an existing CSV file with new flight data from HTML pages.

**Usage:**

```bash
python fmsave.py upcsv <geonames_username> <html_path> <existing.csv> [<output.csv> --before=DD-MM-YYYY --after=DD-MM-YYYY]
```

**Arguments:**

- `<geonames_username>`: Your GeoNames username
- `<html_path>`: Directory containing new HTML files
- `<existing.csv>`: Path to existing CSV file
- `<output.csv>`: (Optional) Output file; if omitted, updates `<existing.csv>` in place
- `--before=DD-MM-YYYY`: (Optional) Remove/replace flights before this date
- `--after=DD-MM-YYYY`: (Optional) Remove/replace flights after this date

**Examples:**

```bash
# Update with new flights
python fmsave.py upcsv mygeouser ~/flights/html-new/ ~/flights/data.csv

# Replace flights from 2023 onwards
python fmsave.py upcsv mygeouser ~/flights/html-new/ ~/flights/data.csv --after=01-01-2023

# Update specific date range
python fmsave.py upcsv mygeouser ~/flights/html-new/ ~/flights/data.csv ~/flights/updated.csv --after=01-01-2023 --before=31-12-2023
```

---

### `uptz` - Update Timezone Information

Updates missing timezone information in an existing CSV file. Useful when you hit GeoNames API limits during initial conversion.

**Usage:**

```bash
python fmsave.py uptz <geonames_username> <input.csv> [<output.csv>]
```

**Arguments:**

- `<geonames_username>`: Your GeoNames username
- `<input.csv>`: CSV file to update
- `<output.csv>`: (Optional) Output file; if omitted, updates `<input.csv>` in place

**Example:**

```bash
python fmsave.py uptz mygeouser ~/flights/data.csv
```

---

### `validate` - Validate Flight Data

Validates that flight distances and times are consistent and reasonable.

**Usage:**

```bash
python fmsave.py validate <input.csv> [<output.csv>]
```

**Arguments:**

- `<input.csv>`: CSV file to validate
- `<output.csv>`: (Optional) Output file; if omitted, updates `<input.csv>` in place

**Example:**

```bash
python fmsave.py validate ~/flights/data.csv
```

---

### `upair` - Update Airport Data

Updates the airport information database from OurAirports.

**Usage:**

```bash
python fmsave.py upair [<airport_url>]
```

**Arguments:**

- `<airport_url>`: (Optional) Custom URL to download airport data; defaults to <https://davidmegginson.github.io/ourairports-data/airports.csv>

**Examples:**

```bash
# Update from default source
python fmsave.py upair

# Update from custom URL
python fmsave.py upair https://example.com/airports.csv
```

---

### `upof` - Update OpenFlights Data

Updates OpenFlights reference data (airlines, airports, planes).

**Usage:**

```bash
python fmsave.py upof
```

**Example:**

```bash
python fmsave.py upof
```

---

### `upwiki` - Update Wikipedia Aircraft Codes

Updates IATA and ICAO aircraft type codes from Wikipedia.

**Usage:**

```bash
python fmsave.py upwiki
```

**Example:**

```bash
python fmsave.py upwiki
```

---

### `export` - Export to Other Formats

Exports fmsave CSV data to formats compatible with other flight tracking websites.

**Usage:**

```bash
python fmsave.py export <format> <input.csv> [<output.csv>]
```

**Arguments:**

- `<format>`: Export format; one of: `openflights`, `myflightpath`
- `<input.csv>`: Input CSV file
- `<output.csv>`: (Optional) Output file; if omitted, uses `<input.csv>` name with format suffix

**Examples:**

```bash
# Export to OpenFlights format
python fmsave.py export openflights ~/flights/data.csv ~/flights/openflights.csv

# Export to MyFlightPath format
python fmsave.py export myflightpath ~/flights/data.csv ~/flights/myflightpath.csv
```

---

## Troubleshooting

### GeoNames Rate Limit Exceeded

**Problem:** `tocsv` or `upcsv` stops with API limit error

**Solution:**

1. Wait at least 1 hour (free tier: 1,000 calls/hour limit)
2. Run `uptz` to fill in missing timezone data:

   ```bash
   python fmsave.py uptz <geonames_username> <flights.csv>
   ```

3. Consider spreading large conversions across multiple hours

**Prevention:**

- Use `upcsv` instead of `tocsv` for incremental updates
- Process flights in smaller batches using `--max-pages` option

---

### Selenium/Chrome Issues

**Problem:** `dlhtml` fails with Chrome or Selenium errors

**Solutions:**

1. **Chrome not found:**

   ```bash
   # Specify custom Chrome path
   python fmsave.py dlhtml <username> <path> /usr/bin/google-chrome
   ```

2. **Chrome version mismatch:**
   - Update Chrome/Chromium to latest version
   - Update dependencies: `poetry update selenium`

3. **Headless mode issues:**
   - Edit `src/defaults.py` and modify `CHROME_OPTIONS` if needed

---

### Missing Airport Data

**Problem:** Airports not found or missing coordinates

**Solution:**

1. Update airport database:

   ```bash
   python fmsave.py upair
   ```

2. If issue persists, check if airport exists in OurAirports database
3. Update OpenFlights data:

   ```bash
   python fmsave.py upof
   ```

---

### Password Not Prompted

**Problem:** Script doesn't ask for password

**Solution:**

- Ensure you're running in an interactive terminal
- The password prompt uses `getpass` which requires a TTY
- If running in a script, you may need to modify `src/logins.py`

---

## Project Structure

``` bash
fmsave/
├── src/
│   ├── fmsave.py         # Main entry point and CLI
│   ├── fmdownload.py     # FlightMemory download and parsing
│   ├── fmvalidate.py     # Flight data validation
│   ├── dataexport.py     # Export to other formats
│   ├── geonames.py       # GeoNames API integration
│   ├── logins.py         # Authentication handling
│   ├── lookups.py        # Airport/airline lookups
│   ├── data.py           # Data file management
│   ├── utils.py          # Utility functions
│   ├── constants.py      # Constants and mappings
│   ├── defaults.py       # Default configuration
│   ├── exec.py           # Execution helpers
│   └── logging.yaml      # Logging configuration
├── data/
│   ├── fmsave/           # FlightMemory data mappings
│   ├── ourairports/      # OurAirports airport data
│   ├── openflights/      # OpenFlights reference data
│   ├── wiki/             # Wikipedia aircraft codes
│   └── myflightpath/     # MyFlightPath export config
├── README.md             # This file
├── pyproject.toml        # Poetry dependencies
└── LICENSE               # MIT License
```

---

## License

MIT License - see LICENSE file for details
