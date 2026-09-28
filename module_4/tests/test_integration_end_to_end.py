"""Task 5: test integration workflow: pull -> update -> render against the test database, and repeat pulls."""

import re
import pull_data
import pytest
from bs4 import BeautifulSoup

pytestmark = pytest.mark.integration


def count(connection):
    return connection.execute("SELECT count(*) FROM applicants").fetchone()[0]


def urls(connection):
    return [row[0] for row in connection.execute("SELECT url FROM applicants").fetchall()]


def rendered(client):
    return BeautifulSoup(client.get("/analysis").get_data(as_text=True), "html.parser")


def test_pull_then_update_and_render(end_to_end_app, db_connection, scraped_records):

    client = end_to_end_app.test_client()
    assert count(db_connection) == 0
    assert "0 applicants in the database" in rendered(client).get_text()

    assert client.post("/pull-data").status_code in (200, 202)
    assert count(db_connection) == len(scraped_records)

    assert client.post("/update-analysis").status_code == 200

    page = rendered(client)
    text = page.get_text()
    
    assert f"{len(scraped_records)} applicants in the database" in text

    assert "100.00%" in text, "the international percentage should reflect the pulled rows"

    for percentage in re.findall(r"\d+(?:\.\d+)?%", text):
        assert re.match(r"^\d+\.\d{2}%$", percentage), f"{percentage} has the wrong precision"
    assert page.select(".answer-label"), "the refreshed page renders no Answer: label"


def test_overlapping_pulls_keep_rows_unique(
        end_to_end_app, db_connection, scraped_records, monkeypatch):
    """Tests whether a second pull that repeats earlier records adds only the new one."""
    client = end_to_end_app.test_client()
    client.post("/pull-data")

    overlapping = scraped_records[1:] + [
        dict(scraped_records[0], url="https://example.test/result/4")]
    monkeypatch.setattr(pull_data, "scrape_newest", lambda pages: overlapping)
    client.post("/pull-data")

    stored = urls(db_connection)
    assert len(stored) == len(scraped_records) + 1
    assert len(set(stored)) == len(stored)
