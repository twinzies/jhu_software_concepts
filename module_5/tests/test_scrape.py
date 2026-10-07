"""Coverage for the scraper's parsing helpers for 100% test coverage."""

import json

import pytest
import scrape
from bs4 import BeautifulSoup
from conftest import FakeDriver

pytestmark = pytest.mark.db

# One applicant record for test
RESULTS_HTML = """
<table><tbody>
  <tr>
    <td>Stanford University</td>
    <td><span>Computer Science</span><span>PhD</span></td>
    <td>January 15, 2026</td>
    <td>Accepted on Jan 09</td>
    <td><a href="/result/1">See More</a></td>
  </tr>
  <tr>
    <td><div><div>Fall 2026</div><div>International</div>
             <div class="md:tw-hidden">Fall 2026</div></div></td>
  </tr>
  <tr><td><p>Very happy with this.</p></td></tr>
  <tr><td>a stray row with too few cells</td></tr>
  <tr>
    <td>Carnegie Mellon University</td>
    <td></td>
    <td>January 16, 2026</td>
    <td>Rejected</td>
    <td>no applicant link here</td>
  </tr>
</tbody></table>
"""


@pytest.fixture
def records():
    return scrape.extract_records(BeautifulSoup(RESULTS_HTML, "html.parser"))


@pytest.mark.parametrize(
    ("badge", "field"),
    [("American", "US/International"), ("International", "US/International"),
     ("Other", "US/International"), ("GRE AW 4.00", "GRE AW"), ("GRE V 157", "GRE V"),
     ("GRE 161", "GRE"), ("GPA 3.90", "GPA"), ("Fall 2026", "term")],
)
def test_parse_details_files_each_badge(badge, field):
    assert scrape._parse_details([badge])[field] == badge


def test_parse_details_ignores_an_unknown_badge():
    assert scrape._parse_details(["Masters"])["term"] is None


def test_extract_records_reads_one_applicant(records):
    assert len(records) == 1
    assert records[0]["university"] == "Stanford University"
    assert records[0]["program"] == "Computer Science"
    assert records[0]["degree"] == "PhD"
    assert records[0]["url"] == "https://www.thegradcafe.com/result/1"


def test_extract_records_collects_badges_and_comments(records):
    assert records[0]["details_raw"] == ["Fall 2026", "International"]
    assert records[0]["term"] == "Fall 2026"
    assert records[0]["comments"] == "Very happy with this."


@pytest.mark.parametrize(
    ("spans", "program", "degree"),
    [("", None, None), ("<span>Computer Science</span>", "Computer Science", None)],
)
def test_extract_records_tolerates_missing_program_spans(spans, program, degree):
    html = RESULTS_HTML.replace(
        "<span>Computer Science</span><span>PhD</span>", spans)
    record = scrape.extract_records(BeautifulSoup(html, "html.parser"))[0]

    assert (record["program"], record["degree"]) == (program, degree)


def test_get_next_follows_the_next_link():
    soup = BeautifulSoup('<a href="/survey?page=2">Next</a>', "html.parser")
    assert scrape.get_next(soup, "https://example.test/survey") == \
        "https://example.test/survey?page=2"


def test_get_next_returns_none_on_the_last_page():
    soup = BeautifulSoup('<a href="/survey?page=1">Previous</a>', "html.parser")
    assert scrape.get_next(soup, "https://example.test/survey") is None


def test_resume_point_starts_from_scratch_without_a_log(tmp_path, monkeypatch):
    monkeypatch.setattr(scrape, "PAGE_LOG_PATH", tmp_path / "scraped_pages.jsonl")
    assert scrape._resume_point() == (None, 0)


def test_resume_point_uses_the_newest_logged_next_url(tmp_path, monkeypatch):
    """Blank and half-written lines are skipped rather than stopping the resume."""
    log = tmp_path / "scraped_pages.jsonl"
    log.write_text("\n".join([
        json.dumps({"page": 1, "next_url": "https://example.test/survey?page=2"}),
        "",
        "{half written",
        json.dumps({"page": 2, "next_url": "https://example.test/survey?page=3"}),
        json.dumps({"page": 3, "next_url": None}),
    ]) + "\n", encoding="utf-8")
    monkeypatch.setattr(scrape, "PAGE_LOG_PATH", log)

    assert scrape._resume_point() == ("https://example.test/survey?page=3", 2)


# --- The browser layer, driven by fakes --- #

TWO_APPLICANTS_HTML = """
<table><tbody>
  <tr>
    <td>Stanford University</td><td><span>Computer Science</span></td>
    <td>January 15, 2026</td><td>Accepted</td><td><a href="/result/1">See More</a></td>
  </tr>
  <tr><td><div><div>Fall 2026</div></div></td></tr>
  <tr>
    <td>MIT</td><td><span>Computer Science</span></td>
    <td>January 16, 2026</td><td>Rejected</td><td><a href="/result/2">See More</a></td>
  </tr>
  <tr><td><div><div>Fall 2025</div></div></td></tr>
</tbody></table>
"""


def soup_for(title="Grad Cafe Survey"):
    head = f"<head><title>{title}</title></head>" if title else ""
    return BeautifulSoup(f"<html>{head}<body></body></html>", "html.parser")


def test_extract_records_stops_details_at_the_next_applicant():
    """Detail rows belong to the applicant above them, not the one below."""
    records = scrape.extract_records(BeautifulSoup(TWO_APPLICANTS_HTML, "html.parser"))

    assert [record["term"] for record in records] == ["Fall 2026", "Fall 2025"]


def test_start_driver_opens_a_headless_browser(monkeypatch):
    built = {}

    class FakeOptions:
        def __init__(self):
            self.page_load_strategy = None
            self.arguments = []

        def add_argument(self, argument):
            self.arguments.append(argument)

    monkeypatch.setattr(scrape.webdriver, "FirefoxOptions", FakeOptions)
    monkeypatch.setattr(scrape.webdriver, "Firefox", lambda options: built.setdefault("options", options))

    driver = scrape.start_driver()

    assert driver.page_load_strategy == "eager"
    assert "-headless" in driver.arguments


@pytest.mark.parametrize(("times_out", "expected"), [(False, True), (True, False)])
def test_wait_for_results(monkeypatch, times_out, expected):
    """A timeout means no rows appeared, which the caller treats as a failed render."""
    class FakeWait:
        def __init__(self, driver, timeout):
            pass

        def until(self, condition):
            if times_out:
                raise scrape.TimeoutException()
            return True

    monkeypatch.setattr(scrape, "WebDriverWait", FakeWait)

    assert scrape._wait_for_results(FakeDriver()) is expected


@pytest.fixture
def no_sleeping(monkeypatch):
    """Back-off waits are production behaviour, not something tests should sit through."""
    monkeypatch.setattr(scrape.time, "sleep", lambda seconds: None)


def test_load_page_returns_the_parsed_page(monkeypatch, no_sleeping):
    driver = FakeDriver("<html><title>Survey</title></html>")
    monkeypatch.setattr(scrape, "_wait_for_results", lambda current: True)

    returned, soup = scrape.load_page(driver, "https://example.test/survey")

    assert returned is driver
    assert driver.loaded == ["https://example.test/survey"]
    assert soup.title.get_text() == "Survey"


def test_load_page_reloads_then_accepts_a_page_with_no_rows(monkeypatch, no_sleeping, capsys):
    """After three reloads the page is accepted as genuinely empty."""
    driver = FakeDriver()
    monkeypatch.setattr(scrape, "_wait_for_results", lambda current: False)

    scrape.load_page(driver, "https://example.test/survey")

    assert len(driver.loaded) == 4
    assert capsys.readouterr().out.count("No applicant rows appeared") == 3


def test_load_page_restarts_the_driver_after_a_timeout(monkeypatch, no_sleeping, capsys):
    """A driver that times out is replaced, even when it also refuses to close."""
    stale = FakeDriver()
    stale.quit_error = RuntimeError("already dead")
    fresh = FakeDriver()

    def get(url):
        raise scrape.ReadTimeoutError(None, url, "read timed out")

    stale.get = get
    monkeypatch.setattr(scrape, "start_driver", lambda: fresh)
    monkeypatch.setattr(scrape, "_wait_for_results", lambda current: True)

    returned, _ = scrape.load_page(stale, "https://example.test/survey")

    printed = capsys.readouterr().out
    assert returned is fresh
    assert "Browser driver timed out" in printed
    assert "Could not close browser driver" in printed


def test_load_page_gives_up_after_four_timeouts(monkeypatch, no_sleeping):
    driver = FakeDriver()

    def get(url):
        raise scrape.ReadTimeoutError(None, url, "read timed out")

    driver.get = get
    monkeypatch.setattr(scrape, "start_driver", lambda: driver)

    with pytest.raises(scrape.ReadTimeoutError):
        scrape.load_page(driver, "https://example.test/survey")


# --- scrape_data --- #

@pytest.fixture
def scrape_env(tmp_path, monkeypatch, no_sleeping):
    """Point scrape_data at files under tmp_path and a fake browser."""
    driver = FakeDriver()
    output = tmp_path / "data" / "scraped_data.jsonl"
    monkeypatch.setattr(scrape, "OUTPUT_PATH", output)
    monkeypatch.setattr(scrape, "PAGE_LOG_PATH", output.with_name("scraped_pages.jsonl"))
    monkeypatch.setattr(scrape, "start_driver", lambda: driver)
    return driver


def wire_pages(monkeypatch, soups, records, next_urls):
    """Feed scrape_data a fixed sequence of pages without touching a browser."""
    pages, links = iter(soups), iter(next_urls)
    monkeypatch.setattr(scrape, "load_page", lambda driver, url: (driver, next(pages)))
    monkeypatch.setattr(scrape, "extract_records", lambda soup: records)
    monkeypatch.setattr(scrape, "get_next", lambda soup, url: next(links))


def saved(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_scrape_data_saves_records_and_follows_pagination(scrape_env, monkeypatch,
                                                          scraped_records, capsys):
    """Two pages are walked, then the missing next link stops the run."""
    wire_pages(monkeypatch, [soup_for(), soup_for()], scraped_records[:1],
               ["https://example.test/survey?page=2", None])

    scrape.scrape_data()

    assert len(saved(scrape.OUTPUT_PATH)) == 1, "the repeated record is saved only once"
    assert [entry["page"] for entry in saved(scrape.PAGE_LOG_PATH)] == [1, 2]
    assert "No next-page URL found" in capsys.readouterr().out


def test_scrape_data_skips_records_already_on_disk(scrape_env, monkeypatch, scraped_records):
    """URLs already in the output file are not written again."""
    scrape.OUTPUT_PATH.parent.mkdir(parents=True)
    scrape.OUTPUT_PATH.write_text(json.dumps(scraped_records[0]) + "\n\n", encoding="utf-8")
    wire_pages(monkeypatch, [soup_for()], scraped_records[:1], [None])

    scrape.scrape_data()

    assert len(saved(scrape.OUTPUT_PATH)) == 1


def test_scrape_data_tolerates_a_page_without_a_title(scrape_env, monkeypatch,
                                                      scraped_records, capsys):
    wire_pages(monkeypatch, [soup_for(title=None)], scraped_records[:1], [None])

    scrape.scrape_data()

    assert "No title found" in capsys.readouterr().out
    assert saved(scrape.PAGE_LOG_PATH)[0]["title"] is None


def test_scrape_data_resumes_from_the_page_log(scrape_env, monkeypatch, scraped_records):
    """A previous run's next URL decides where this one starts."""
    scrape.PAGE_LOG_PATH.parent.mkdir(parents=True)
    scrape.PAGE_LOG_PATH.write_text(
        json.dumps({"page": 7, "next_url": "https://example.test/survey?page=8"}) + "\n",
        encoding="utf-8")
    wire_pages(monkeypatch, [soup_for()], scraped_records[:1], [None])

    scrape.scrape_data()

    assert saved(scrape.PAGE_LOG_PATH)[-1]["page"] == 8


@pytest.mark.parametrize(
    ("error", "message"),
    [(RuntimeError("HTTP 403 forbidden"), "HTTP request failed"),
     (scrape.ReadTimeoutError(None, "url", "read timed out"), "Browser driver timed out")],
)
def test_scrape_data_reports_recoverable_failures(scrape_env, monkeypatch, capsys,
                                                  error, message):
    """A blocked request or a dead driver stops the run without losing saved records."""
    def failing(driver, url):
        raise error

    monkeypatch.setattr(scrape, "load_page", failing)

    scrape.scrape_data()

    assert message in capsys.readouterr().out


def test_scrape_data_reraises_an_unexpected_error(scrape_env, monkeypatch):
    def failing(driver, url):
        raise ValueError("something else entirely")

    monkeypatch.setattr(scrape, "load_page", failing)

    with pytest.raises(ValueError, match="something else entirely"):
        scrape.scrape_data()


def test_scrape_data_reports_a_driver_that_will_not_close(scrape_env, monkeypatch,
                                                          scraped_records, capsys):
    scrape_env.quit_error = RuntimeError("already dead")
    wire_pages(monkeypatch, [soup_for()], scraped_records[:1], [None])

    scrape.scrape_data()

    assert "Could not close browser driver" in capsys.readouterr().out
