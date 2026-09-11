import json
from pathlib import Path
from pprint import pprint
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver

BASE_URL = "https://www.thegradcafe.com/survey"

OUTPUT_PATH = Path(__file__).parent / "data" / "gradcafe_records.jsonl"

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

    pprint(records[0])
    print(f"Extracted {len(records)} applicants")
    return records

def get_next(soup, url)->str:
    """Returns the URL for the next page from the html."""
    links = soup.find_all("a", href=True)

    next_link = next((page_link for page_link in links if page_link.get_text(" ", strip=True).casefold() == "next"),None,)

    next_url = urljoin(url, next_link["href"]) if next_link else None
    return next_url

if __name__ == "__main__":

    print("Running scrape script...")

    # Open the URL in a windowless browser to bypass the 403 Error.
    options = webdriver.FirefoxOptions()
    options.add_argument("-headless")

    driver = webdriver.Firefox(options)

    try: 
        # Get the html from the first page.
        url = BASE_URL
        driver.get(url)
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        print(soup.title.get_text() if soup.title else "No title found")

        OUTPUT_PATH.parent.mkdir(exist_ok=True)
        saved_urls = set()
        if OUTPUT_PATH.exists():
            with open(OUTPUT_PATH, encoding="utf-8") as jsonl_file:
                saved_urls = {json.loads(line)["url"] for line in jsonl_file if line.strip()}

        saved_count = 0

        for _ in range(2500):
            records = extract_records(soup) # Gets the records from the current page.

            # Append each record before loading the next; closing flushes the file.
            with open(OUTPUT_PATH, "a", encoding="utf-8") as jsonl_file:
                for record in records:
                    if record["url"] not in saved_urls:
                        jsonl_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                        saved_urls.add(record["url"])
                        saved_count += 1

            print(f"Saved {saved_count} new records.. completed page{_+1}/2500.")

            # Update URL for next page and get the html.
            url = get_next(soup, url)
            
            driver.get(url)
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")

    except Exception as error:
        if "400" in str(error) or "403" in str(error):
            print(f"HTTP request failed: {error}")
        else:
            raise
    
    finally:
        driver.quit()


    
