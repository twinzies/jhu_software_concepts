"""Pull Data: scrape the newest Grad Cafe pages and load them into PostgreSQL.
"""

import json
import sys
import time
from pathlib import Path

import psycopg

# Python puts this script's folder (src/) on sys.path, so sibling modules import directly.
import clean
import load_data
import scrape

BASE_DIR = Path(__file__).resolve().parent
STATUS_PATH = BASE_DIR / "pull_status.json"

# Number of pages to pull data from.
NUM_PAGES = 3


def scrape_newest(pages):
    """Scrape up to the given number of pages, starting from the newest results."""
    # Starts at BASE_URL, not scrape_data()'s resume point, which is deep in the archive.
    driver = scrape.start_driver()
    records, url = [], scrape.BASE_URL
    try:
        driver, soup = scrape.load_page(driver, url)
        for _ in range(pages):
            records.extend(scrape.extract_records(soup))
            url = scrape.get_next(soup, url)
            if url is None:
                break
            time.sleep(1)
            driver, soup = scrape.load_page(driver, url)
    finally:
        driver.quit()
    return records


def save_raw(records, path):
    """Append records whose URL is not already in the Module 2 scrape file."""
    seen = set()
    if path.exists():
        with open(path, encoding="utf-8") as raw_file:
            seen = {json.loads(line)["url"] for line in raw_file if line.strip()}

    fresh = [record for record in records if record["url"] not in seen]
    path.parent.mkdir(exist_ok=True)
    with open(path, "a", encoding="utf-8") as raw_file:
        raw_file.writelines(json.dumps(record, ensure_ascii=False) + "\n" for record in fresh)
    return fresh


def main():
    """Scrape, clean and load new entries, recording the outcome in STATUS_PATH."""
    try:
        scraped = scrape_newest(NUM_PAGES)
        fresh = save_raw(scraped, scrape.OUTPUT_PATH)
        cleaned = clean.clean_data(fresh)
        rows = [load_data.to_row(record, position)
                for position, record in enumerate(cleaned, start=1)]

        inserted = 0
        if rows:
            with psycopg.connect(connect_timeout=10) as connection:
                inserted, _ = load_data.load_records(connection, rows)

        # Counts entries dropped as already-seen by either the scrape file or the loader.
        status = {"state": "finished", "scraped": len(scraped), "inserted": inserted,
                  "skipped": len(scraped) - inserted, "message": ""}
        print(f"Scraped {status['scraped']}; inserted {inserted}; skipped {status['skipped']}.")
    # Any failure must still be written to the status file for the Flask page.
    except Exception as error:  # pylint: disable=broad-exception-caught
        status = {"state": "failed", "scraped": 0, "inserted": 0, "skipped": 0,
                  "message": f"{type(error).__name__}: {error}"}
        print(status["message"], file=sys.stderr)

    status["finished"] = time.time()
    STATUS_PATH.write_text(json.dumps(status), encoding="utf-8")
    return 0 if status["state"] == "finished" else 1


if __name__ == "__main__":
    main()
