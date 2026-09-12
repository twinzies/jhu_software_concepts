# Module 2: Web Scraping

## Project Description

Scrapes graduate admission results from [The GradCafe](https://www.thegradcafe.com/survey),
cleans them into a structured JSON object, and standardizes the program and university names
using a locally hosted LLM. The result is 31,640 applicant entries in `applicant_data.json`.

## Quick Start Guide

From the `module_2` folder:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scrape.py    # -> data/scraped_data.jsonl
python clean.py     # -> applicant_data.json
```

Then standardize the program and university names:

```bash
pip install -r llm_hosting/requirements.txt
cd llm_hosting && python parallel_run.py   # -> ../llm_extend_applicant_data.json
```

Both `scrape.py` and `parallel_run.py` resume where a previous run stopped, so either can be
interrupted and restarted without losing work or duplicating records.

Requires Python 3.10 or higher.

## robots.txt compliance

`https://www.thegradcafe.com/robots.txt` was checked before scraping; `screenshot.jpg` is the
evidence.

The `User-agent: *` rules are `Allow: /`, followed by a block disallowing only account pages:
`/signin`, `/register`, `/forgot-password`, `/reset-password`, `/confirm-password`,
`/verify-email` and `/profile`. This scraper reads only `/survey`, the public paginated
results listing, and records the `/result/<id>` links it finds there. Neither path is
disallowed, so the scrape is permitted.

There is no `Crawl-delay` directive, but the scraper still waits one second between pages. It
stops on a 400 or 403 response, and never signs in, solves a CAPTCHA, or requests a
disallowed path.

## Approach

**Scraping** is a hybrid workflow. `urllib.parse.urljoin` builds and resolves the page URLs,
headless **Firefox + GeckoDriver** (resolved automatically by Selenium Manager) renders the
JavaScript-loaded results table, and BeautifulSoup parses the rendered HTML. Pages use the
`eager` load strategy followed by an explicit `WebDriverWait` for an applicant row, rather
than a fixed sleep.

Records are appended after each page, and every page's `next_url` is logged to
`data/scraped_pages.jsonl`, which is what makes a run resumable. A driver timeout quits and
restarts the browser; a page that renders no rows is reloaded rather than mistaken for the end
of the results.

**Cleaning** joins the program and university into the single `program` string the
standardizer expects, and splits `"Accepted on Jan 09"` into `status` and `decision_date`. The
raw `status_raw` and `details_raw` fields are kept alongside the cleaned ones for
traceability. Unavailable values are `null` throughout.

**Standardization** runs the provided `llm_hosting/app.py` model over every record. See
[llm_hosting/README.md](llm_hosting/README.md) for the local additions.

## Module repository structure

```
module_2/
├── scrape.py                        # scraping logic
├── clean.py                         # cleaning logic
├── applicant_data.json              # cleaned records
├── llm_extend_applicant_data.json   # llm standardized output
├── screenshot.png                   # robots.txt evidence
├── requirements.txt
├── README.md                        # this file
├── README.txt
├── data/
│   ├── scraped_data.jsonl           # raw scraped records
│   └── scraped_pages.jsonl          # page urls/logs - for resuming a run
└── llm_hosting/                     # mostly provided
    ├── app.py
    ├── parallel_run.py              # added script: parallelization and resume
    ├── canon_programs.txt
    ├── canon_universities.txt
    └── README.md                   
```

## Known limitations

- The LLM's post-processing title-cases its output, which mangles acronyms: `ACMS` becomes
  `Acms`, `ETH Zurich` becomes `Eth Zurich`, `PhD` becomes `Phd`. The original `program` field is preserved on every record, so this is recoverable.
- Blocking is detected by matching `"400"`/`"403"` in the driver's exception text. Selenium renders an error page instead of raising, so a block would more likely surface as a page with no applicant rows.
- 8 of 31,640 records have no program name on the site; those rows fall back to the
  university name alone.

## Project Status

[Completed]
