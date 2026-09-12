Please see the markdown file - README.md for a fuller description, including the
robots.txt compliance notes and the repository structure.

NAME
Tara Jain (JHED: kjain4)

MODULE INFO
Module 2 - Assignment: Web Scraping
Due Sunday 13 September 2026, 11:59pm

APPROACH

Gathering the data (scrape.py)
The site blocks plain requests and builds its results table with JavaScript, so the scraper drives a headless Firefox browser (to keep it as lightweight as possible) and reads the finished page with BeautifulSoup. I found this approach to work better than the recommendation to manually bypass verification in an open browser, and though mechanical soup and its stateful browser were attempted -it hit the 403 status error. 
Every page is saved before the next is fetched, and the link to the next page is written to scraped_pages.json, so a new run continues from where the last one stopped instead of starting over. If the browser stalls it is quit and restarted, and a page that comes back empty is reloaded
rather than treated as the end of the results - I found this to be especially helpful as the headless browser would, at times, be too slow and timeout - which is why the “eager” strategy was picked which does not wait for images to load in the headless browser.

Cleaning the data (clean.py)
clean_data() reshapes each scraped record as per the output expected by the assignment. The program and university names are joined into the single "program" string the llm standardizer expects, and a status such as
"Accepted on Jan 09" is split by _normalize_status() into "status" and "decision_date” so the acceptance or rejection date is its own field. The html was already cleaned by beautiful soup in the previous step (scrape.py).

Standardizing with the local LLM (llm_hosting/)
parallel_run.py was added beside it and calls the same
_call_llm function, differing from the stock CLI in three ways. It deduplicates: the 31,640 rows contain only 12,540 distinct program strings, so each is standardized once
and mapped back, cutting the model calls by 2.5x. It runs several worker processes, each loading its own copy of the model. And it caches every result to llm_cache.jsonl as it
goes, so an interrupted run resumes instead of starting over, and refuses to write a partial output file. On Apple Silicon (my laptop configuration) it defaults to MPS (which gives a 2.5x boost over CPU) and I picked three workers. 

KNOWN BUGS

The LLM's post-processing title-cases its output, so acronyms come back mangled: ACMS as "Acms", ETH Zurich as "Eth Zurich", PhD as "Phd". The original program field is preserved on every record, so nothing is lost. Fixing it means adding an acronym exception list to _post_normalize_university and _post_normalize_program in app.py, or extending canon_universities.txt so the fuzzy match reaches the correct name first.

Blocking is detected by looking for "400" or "403" in the browser driver's exception text. Selenium renders an HTTP error page rather than raising, so a real block would
more likely appear as a page with no applicant rows. That case is currently retried three times and then accepted as the end of the results. Checking the page title or the
extracted record count would detect a block properly, though I found the page titles for this website to not provide useful information about the error.

8 of the 31,640 records have no program name on GradCafe.