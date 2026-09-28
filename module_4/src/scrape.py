"""Scrape Grad Cafe results with headless Firefox and parse them with BeautifulSoup."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait
from urllib3.exceptions import ReadTimeoutError

BASE_URL = "https://www.thegradcafe.com/survey"

OUTPUT_PATH = Path(__file__).parent / "data" / "scraped_data.jsonl"

# For picking starting from the url the script stopped at, instead of rescraping from page 1.
PAGE_LOG_PATH = OUTPUT_PATH.with_name("scraped_pages.jsonl")

def _parse_details(badges):
    """Splits the applicant badges into the fields the assignment asks for."""
    details = {"term": None, "US/International": None,
               "GRE": None, "GRE V": None, "GRE AW": None, "GPA": None}

    for badge in badges:
        # The longer GRE labels have to be tested before the plain "GRE " prefix.
        if badge in ("American", "International", "Other"):
            details["US/International"] = badge
        elif badge.startswith("GRE AW "):
            details["GRE AW"] = badge
        elif badge.startswith("GRE V "):
            details["GRE V"] = badge
        elif badge.startswith("GRE "):
            details["GRE"] = badge
        elif badge.startswith("GPA "):
            details["GPA"] = badge
        elif badge.partition(" ")[2].isdigit():
            details["term"] = badge

    return details

def extract_records(soup)->list[dict]:
    """Extracts admission records from the html."""
    records = []
    for row in soup.select("tbody tr"):
        cells = row.find_all("td", recursive=False)
        link = row.select_one('a[href^="/result/"]')

        # A main applicant row has five cells and an applicant link.
        if len(cells) != 5 or link is None:
            continue

        program_parts = cells[1].find_all("span")

        # Collect the following detail/comment rows.
        extra_rows = []
        sibling = row.find_next_sibling("tr")

        while sibling is not None:
            if sibling.select_one('a[href^="/result/"]'):
                break  # The next applicant starts here.

            extra_rows.append(sibling)
            sibling = sibling.find_next_sibling("tr")

        # Badges contain term, applicant type, and academic metrics.
        badges = [
            badge.get_text(" ", strip=True)
            for extra in extra_rows
            for badge in extra.select("td > div > div")
            if "md:tw-hidden" not in badge.get("class", [])
        ]

        comments = [
            paragraph.get_text(" ", strip=True)
            for extra in extra_rows
            for paragraph in extra.find_all("p")
        ]

        record = {
            "university": cells[0].get_text(" ", strip=True),
            "program": program_parts[0].get_text(strip=True)
                if program_parts else None,
            "degree": program_parts[1].get_text(strip=True)
                if len(program_parts) > 1 else None,
            **_parse_details(badges),
            "date_added": cells[2].get_text(" ", strip=True),
            "status_raw": cells[3].get_text(" ", strip=True),
            "url": urljoin("https://www.thegradcafe.com", link["href"]),
            "details_raw": badges,
            "comments": "\n".join(comments) or None,
            "raw_text": "\n".join(
                part.get_text(" ", strip=True)
                for part in [row, *extra_rows]
            ),
        }

        records.append(record)

    print(f"Extracted {len(records)} applicants")
    return records

def get_next(soup, url)->str:
    """Returns the URL for the next page from the html."""
    links = soup.find_all("a", href=True)

    next_link = next((page_link for page_link in links if page_link.get_text(" ", strip=True).casefold() == "next"),None,)

    next_url = urljoin(url, next_link["href"]) if next_link else None
    return next_url

def _start_driver():
    """Opens a windowless browser so JavaScript-rendered results load."""
    options = webdriver.FirefoxOptions()
    options.page_load_strategy = "eager"
    options.add_argument("-headless")

    return webdriver.Firefox(options)

def _wait_for_results(driver):
    """Waits for the applicant rows to render before the page is read.

    The eager load strategy returns as soon as the HTML parses, so the
    results table may still be on its way. Waiting for a row to appear is
    both quicker and more reliable than sleeping for a fixed time.

    Returns whether any applicant rows appeared.
    """
    try:
        WebDriverWait(driver, 30).until(
            expected_conditions.presence_of_element_located(
                (By.CSS_SELECTOR, 'tbody tr a[href^="/result/"]')
            )
        )
        return True
    except TimeoutException:
        return False

def _load_page(driver, url):
    """Loads a page, restarting the browser driver if it times out.

    Returns the driver along with the parsed page, since a restart replaces
    the driver the caller handed in.
    """
    for attempt in range(4):
        try:
            driver.get(url)

            if not _wait_for_results(driver) and attempt < 3:
                # An empty page usually means a failed render, so reload before accepting it.
                print(f"No applicant rows appeared; reloading ({attempt + 1}/3).")
                time.sleep(5)
                continue

            return driver, BeautifulSoup(driver.page_source, "html.parser")

        except ReadTimeoutError:
            if attempt == 3:
                raise

            print(f"Browser driver timed out; restarting ({attempt + 1}/3).")

            try:
                driver.quit()
            except Exception as error:
                print(f"Could not close browser driver: {error}")

            time.sleep(5 * (attempt + 1))  # Back off a little longer each time.
            driver = _start_driver()

def _resume_point():
    """Returns the URL and page number to continue from, read from the page log."""
    if not PAGE_LOG_PATH.exists():
        return None, 0

    # Use the newest page that recorded a next URL.
    resume_url, resume_page = None, 0
    with open(PAGE_LOG_PATH, encoding="utf-8") as page_log:
        for line in page_log:
            if not line.strip():
                continue

            try:
                logged_page = json.loads(line)
            except json.JSONDecodeError:
                continue  # Skip line left half-written.

            if logged_page.get("next_url"):
                resume_url = logged_page["next_url"]
                resume_page = logged_page.get("page", 0)

    return resume_url, resume_page

def scrape_data():
    """Pull applicant data from Grad Cafe."""
    run_started = datetime.now(timezone.utc).isoformat()
    print("Running scrape script...")

    # Pick up where the previous run stopped.
    resume_url, resume_page = _resume_point()
    url = resume_url or BASE_URL
    print(f"Starting at page {resume_page + 1}: {url}")

    driver = _start_driver()

    try:
        # Get the html from the first page.
        driver, soup = _load_page(driver, url)

        print(soup.title.get_text() if soup.title else "No title found")

        OUTPUT_PATH.parent.mkdir(exist_ok=True)
        saved_urls = set()
        if OUTPUT_PATH.exists():
            with open(OUTPUT_PATH, encoding="utf-8") as jsonl_file:
                saved_urls = {json.loads(line)["url"] for line in jsonl_file if line.strip()}

        saved_count = 0

        for i in range(2500):
            records = extract_records(soup) # Gets the records from the current page.
            saved_before_page = saved_count
            page_number = resume_page + i + 1

            # Append each record and closing the file.
            with open(OUTPUT_PATH, "a", encoding="utf-8") as jsonl_file:
                for record in records:
                    if record["url"] not in saved_urls:
                        jsonl_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                        saved_urls.add(record["url"])
                        saved_count += 1

            next_url = get_next(soup, url)
            new_records = saved_count - saved_before_page
            
            # Save pagination evidence even when every applicant is a duplicate.
            with open(PAGE_LOG_PATH, "a", encoding="utf-8") as page_log:
                page_log.write(json.dumps({
                    "run_started": run_started,
                    "page": page_number,
                    "requested_url": url,
                    "browser_url": driver.current_url,
                    "next_url": next_url,
                    "title": soup.title.get_text(strip=True) if soup.title else None,
                    "extracted_records": len(records),
                    "new_records": new_records,
                    "applicant_urls": [record["url"] for record in records],
                }, ensure_ascii=False) + "\n")

            print(f"Saved {new_records} new records this page ({saved_count} this run).. completed page {page_number} ({i+1}/2500 this run).")

            # Update URL for next page and get the html.
            if next_url is None:
                print("No next-page URL found; stopping. See the page log for details.")
                break
            url = next_url

            time.sleep(1)  # Throttle requests; content waits happen in _load_page.
            driver, soup = _load_page(driver, url)

    except Exception as error:
        if "400" in str(error) or "403" in str(error):
            print(f"HTTP request failed: {error}")
        elif isinstance(error, ReadTimeoutError):
            print("Browser driver timed out. Scraping stopped; previously saved records are preserved.")
        else:
            raise

    finally:
        try:
            driver.quit()
        except Exception as error:
            print(f"Could not close browser driver: {error}")

if __name__ == "__main__":
    scrape_data()
