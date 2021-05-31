# Crawler

Python library to extract Google News to per-day csv files.

## Requirement

[`pygooglenews`](https://github.com/kotartemiy/pygooglenews) library

[`Newspaper3k`](https://github.com/codelucas/newspaper) library

## Usage

This library use
```
"asian hate crime" AND ("report" OR "incident")
```
as the query string for `https://news.google.com/`.

The per-day csv files are formated as `"asian_hate_crime_%Y-%m-%d.csv"`

In `crawler.py`:

Using the `make_csv_from_google_news_for_yesterday()` to periodly generate latest csv file.

Using the `make_csv_from_google_news_for_range()` to generate csv files for a given time range. Example:
```
# Generate csv files for 50 days ending today
import datetime
make_csv_from_google_news_for_range(datetime.datetime.now(), 50)
```

## Issue

Cannot determine if a entry of the response is reporting an asain hate crime incident and extract the time and location from the text. Need more nature language processing library to do so.