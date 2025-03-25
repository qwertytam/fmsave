# Readme

Save raw HTML from flightmemory.com for further parsing.

Using `pipenv` for virtual environment i.e. `pipenv shell` then `pipenv install`# fmsave

See `src/fmsave.py` for usage details

## First Time Download of HTML and Conversion to csv

```python
>python fmsave.py dlhtml fmuser ~/save/path/
>python fmsave.py tocsv gnuser ~/save/path/ flights.csv
```

If you hit the GeoNames max hourly credit limit of 1,000 API calls, then run

```python
>python fmsave.py uptz gnuser ~/save/path/flights.csv
```

to update the missing time zone information from GeoNames once sufficient time
has passed.
