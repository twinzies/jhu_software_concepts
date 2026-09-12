# Module 2: Web Scraping

## Project Description

Scrapes graduate admission results from [The GradCafe](https://www.thegradcafe.com/survey),
cleans them into a structured JSON object, and standardizes the program and university names
using a locally hosted LLM. The result is 31,640 applicant entries in `applicant_data.json`.

[This](git@github.com:twinzies/jhu_software_concepts.git) is the SSH URL to this project repository.

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

`https://www.thegradcafe.com/robots.txt` was checked before scraping; see `screenshot.jpg` for evidence.

The `User-agent: *` rules are `Allow: /`, followed by a block disallowing only account pages: `/signin`, `/register`, `/forgot-password`, `/reset-password`, `/confirm-password`, `/verify-email` and `/profile`. This scraper reads only `/survey`, the public paginated results listing, and records the `/result/<id>` links it finds there. Neither path is disallowed, so the scrape is permitted.

## Approach

**Scraping the data (scrape.py)**
The site blocks plain requests and builds its results table with JavaScript, so the scraper drives a headless Firefox browser (to keep it as lightweight as possible) and reads the finished page with BeautifulSoup. I found this approach to work better than the recommendation to manually bypass verification in an open browser, and though mechanical soup and its stateful browser were attempted -it hit the 403 status error. 

Every page is saved before the next is fetched, and the link to the next page is written to scraped_pages.json, so a new run continues from where the last one stopped instead of starting over. If the browser stalls it is quit and restarted, and a page that comes back empty is reloaded
rather than treated as the end of the results - I found this to be especially helpful as the headless browser would, at times, be too slow and timeout - which is why the “eager” strategy was picked which does not wait for images to load in the headless browser.

**Cleaning the data (clean.py)**
clean_data() reshapes each scraped record as per the output expected by the assignment. The program and university names are joined into the single "program" string the llm standardizer expects, and a status such as
"Accepted on Jan 09" is split by _normalize_status() into "status" and "decision_date” so the acceptance or rejection date is its own field. The html was already cleaned by beautiful soup in the previous step (scrape.py).

**Standardizing with the local LLM (llm_hosting/)**
parallel_run.py was added beside it and calls the same
_call_llm function, differing from the stock CLI in three ways. It deduplicates: the 31,640 rows contain only 12,540 distinct program strings, so each is standardized once and mapped back, cutting the model calls by 2.5x. It runs several worker processes, each loading its own copy of the model. And it caches every result to llm_cache.jsonl as it goes, so an interrupted run resumes instead of starting over, and refuses to write a partial output file. On Apple Silicon (my laptop configuration) it defaults to MPS (which gives a 2.5x boost over CPU) and I picked three workers. 

## Module repository structure

```
module_2/
├── scrape.py                        # scraping logic
├── clean.py                         # cleaning logic
├── applicant_data.json              # cleaned records
├── llm_extend_applicant_data.json   # llm standardized output
├── screenshot.jpg                   # robots.txt evidence
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
