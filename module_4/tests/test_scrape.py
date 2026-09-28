"""Coverage for the scraper's parsing helpers, which need no browser."""

import json

import pytest
import scrape
from bs4 import BeautifulSoup

pytestmark = pytest.mark.db

# One applicant row plus the detail and comment rows that follow it.
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
