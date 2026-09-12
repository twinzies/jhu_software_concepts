Please see the markdown file - README.md for a fuller description, including the
robots.txt compliance notes and the repository structure.

NAME
Tara Jain (JHED: kjain4)

MODULE INFO
Module 2 - Assignment: Web Scraping
Due Sunday 13 September 2026, 11:59pm

APPROACH

Gathering the data (scrape.py)
A hybrid workflow. urllib.parse.urljoin builds and resolves each page URL, a headless
Firefox browser driven by Selenium renders the results table, and BeautifulSoup parses
the rendered HTML. GradCafe loads its results with JavaScript and returns 403 to a plain
urllib request, so the browser is needed to render the page; it is used only to render
publicly accessible pages, never to bypass a restriction.

GeckoDriver is resolved automatically by Selenium Manager, so no driver is checked in or
configured by hand. Pages load with the "eager" strategy and then an explicit
WebDriverWait for an applicant row to appear, rather than a fixed sleep. One second
passes between pages to stay polite.

extract_records() walks the results table. A main applicant row has five cells and a
link to /result/<id>; the detail rows that follow it hold the term, applicant type and
academic metric badges, plus any comment. Those badges are matched by content rather than
position, because the site emits a bare "0" in the applicant-type slot when the value is
unset - 555 records would otherwise be labelled type "0".

Each page is appended to data/scraped_data.jsonl before the next is fetched, and every
page's next_url is logged to data/scraped_pages.jsonl. A new run reads the most recent
logged next_url and continues from there, so an interrupted scrape is never restarted
from page 1. A driver timeout quits the browser and restarts it, up to three consecutive
times with a growing delay; a page that renders no applicant rows is reloaded rather than
mistaken for the end of the results, which is what a blank page otherwise looks like
since it carries no "next" link.

Cleaning the data (clean.py)
clean_data() reshapes each scraped record. The program and university names are joined
into the single "program" string the standardizer expects, and a status such as
"Accepted on Jan 09" is split by _normalize_status() into "status" and "decision_date" so
the acceptance or rejection date is its own field. The raw status_raw and details_raw
fields are kept alongside the cleaned ones for traceability. Anything unavailable is
null, consistently, rather than a mix of null and empty strings. save_data() writes
applicant_data.json and load_data() reads it back.

Standardizing with the local LLM (llm_hosting/)
app.py is used unmodified. parallel_run.py was added beside it and calls the same
_call_llm function, differing from the stock CLI in three ways. It deduplicates: the
31,640 rows contain only 12,540 distinct program strings, so each is standardized once
and mapped back, cutting the model calls by 2.5x. It runs several worker processes, each
loading its own copy of the model. And it caches every result to llm_cache.jsonl as it
goes, so an interrupted run resumes instead of starting over, and refuses to write a
partial output file. On Apple Silicon it defaults to Metal and three workers. These
changes are documented in llm_hosting/README.md.

KNOWN BUGS

The LLM's post-processing title-cases its output, so acronyms come back mangled: ACMS as
"Acms", ETH Zurich as "Eth Zurich", PhD as "Phd". The original program field is preserved
on every record, so nothing is lost. Fixing it means adding an acronym exception list to
_post_normalize_university and _post_normalize_program in app.py, or extending
canon_universities.txt so the fuzzy match reaches the correct name first.

Blocking is detected by looking for "400" or "403" in the browser driver's exception
text. Selenium renders an HTTP error page rather than raising, so a real block would
more likely appear as a page with no applicant rows. That case is currently retried three
times and then accepted as the end of the results. Checking the page title or the
extracted record count would detect a block properly.

8 of the 31,640 records have no program name on GradCafe. Those rows fall back to the
university name alone, so their "program" field holds only a university.
