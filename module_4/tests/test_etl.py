"""Coverage for the ETL modules: clean, load_data, orm_queries, pull_data, query_data."""

import json
from datetime import date
from decimal import Decimal

import psycopg
import pytest

import clean
import load_data
import orm_queries
import pull_data
import query_data
import scrape

pytestmark = pytest.mark.db


# --- clean.py --- #

def test_clean_status_and_round_trips_through_json(tmp_path, scraped_records):
    scraped_path = tmp_path / "scraped_data.jsonl"
    scraped_path.write_text(
        "\n".join(json.dumps(record) for record in scraped_records) + "\n\n",
        encoding="utf-8")

    cleaned = clean.clean_data(clean._load_scraped(scraped_path))
    output = tmp_path / "applicant_data.json"
    clean.save_data(cleaned, output)

    assert clean.load_data(output) == cleaned
    assert cleaned[0]["status"] == "Accepted"
    assert cleaned[0]["decision_date"] == "Jan 09"


def test_clean_handles_for_record_without_a_program_or_decision_date():
    """A blank program and a bare status leave the optional fields empty."""
    record = dict.fromkeys(
        ("comments", "date_added", "url", "term", "US/International",
         "GRE", "GRE V", "GRE AW", "GPA", "details_raw"))
    record.update(program=None, university=None, status_raw="Rejected", degree="PhD")

    cleaned = clean._clean_record(record)

    assert cleaned["program"] is None
    assert (cleaned["status"], cleaned["decision_date"]) == ("Rejected", None)


# --- load_data.py converters --- #

@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, None), ("  Fall 2026 ", "Fall 2026"), ("   ", None)],
)
def test_as_text(value, expected):
    assert load_data.as_text(value, "term") == expected


def test_as_text_rejects_a_non_string():
    with pytest.raises(ValueError, match="expected text"):
        load_data.as_text(7, "term")


@pytest.mark.parametrize(
    ("value", "expected"),
    [("GPA 3.40", 3.4), ("n/a", None), (None, None), (3.5, 3.5)],
)
def test_as_number(value, expected):
    assert load_data.as_number(value, "GPA") == expected


@pytest.mark.parametrize("value", ["not a score", float("inf")])
def test_as_number_rejects_unusable_values(value):
    with pytest.raises(ValueError):
        load_data.as_number(value, "GPA")


@pytest.mark.parametrize(
    ("value", "expected"),
    [("2026-01-15", date(2026, 1, 15)), ("Jan 15, 2026", date(2026, 1, 15)),
     ("January 15, 2026", date(2026, 1, 15)), (None, None)],
)
def test_as_date_accepts_every_grad_cafe_format(value, expected):
    assert load_data.as_date(value, "date_added") == expected


def test_as_date_rejects_unknown_format():
    with pytest.raises(ValueError, match="unrecognized date"):
        load_data.as_date("15/01/2026", "date_added")


def test_to_row_rejects_a_non_dict():
    with pytest.raises(ValueError, match="expected a JSON object"):
        load_data.to_row(["not", "a", "record"], 1)


def test_to_row_reports_the_offending_record_number(scraped_records):
    broken = dict(clean.clean_data(scraped_records)[0], GPA="not a score")

    with pytest.raises(ValueError, match="Record 4:"):
        load_data.to_row(broken, 4)


# --- load_data.py file handling and main --- #

def cleaned_json(tmp_path, scraped_records):
    path = tmp_path / "applicant_data.json"
    path.write_text(json.dumps(clean.clean_data(scraped_records)), encoding="utf-8")
    return path


def test_read_records_reads_every_row(tmp_path, scraped_records):
    rows = load_data.read_records(cleaned_json(tmp_path, scraped_records))
    assert len(rows) == len(scraped_records)


def test_read_records_rejects_a_non_list_file(tmp_path):
    path = tmp_path / "applicant_data.json"
    path.write_text('{"program": "Computer Science"}', encoding="utf-8")

    with pytest.raises(ValueError, match="JSON list"):
        load_data.read_records(path)


def test_load_data_inserts_and_reports(tmp_path, scraped_records, db_connection,
                                            connect_to_test_db, monkeypatch, capsys):
    monkeypatch.setattr(load_data.psycopg, "connect", connect_to_test_db)
    monkeypatch.setattr(
        "sys.argv", ["load_data.py", str(cleaned_json(tmp_path, scraped_records))])

    assert load_data.main() == 0

    assert f"inserted {len(scraped_records):,}" in capsys.readouterr().out


def test_load_data_reports_failure(tmp_path, monkeypatch, capsys):
    missing = tmp_path / "absent.json"
    monkeypatch.setattr("sys.argv", ["load_data.py", str(missing)])

    assert load_data.main() == 1
    assert "Load failed" in capsys.readouterr().err


# --- orm_queries.py --- #

def test_orm_queries_prints_every_question(db_session, monkeypatch, capsys):
    monkeypatch.setattr(orm_queries, "Session", lambda: db_session)

    assert orm_queries.main() == 0

    printed = capsys.readouterr().out
    assert all(f"Q{number}:" in printed for number in orm_queries.QUESTIONS)


def test_orm_queries_reports_db_failure(monkeypatch, capsys):
    def broken():
        raise orm_queries.SQLAlchemyError("connection refused")

    monkeypatch.setattr(orm_queries, "Session", broken)

    assert orm_queries.main() == 1
    assert "ORM analysis failed" in capsys.readouterr().err


# --- pull_data.py --- #

class FakeDriver:
    """A webdriver stand-in recording the pages it was asked to load."""

    def __init__(self):
        self.quit_calls = 0
        self.current_url = "https://example.test/survey"

    def quit(self):
        self.quit_calls += 1


def test_scrape_newest_walks_requested_pages(monkeypatch, scraped_records):
    """Paging stops after the requested number of pages."""
    driver = FakeDriver()
    pages = iter(["https://example.test/survey?page=2", None])
    monkeypatch.setattr(scrape, "_start_driver", lambda: driver)
    monkeypatch.setattr(scrape, "_load_page", lambda current, url: (current, url))
    monkeypatch.setattr(scrape, "extract_records", lambda soup: [scraped_records[0]])
    monkeypatch.setattr(scrape, "get_next", lambda soup, url: next(pages))
    monkeypatch.setattr(pull_data.time, "sleep", lambda seconds: None)

    records = pull_data.scrape_newest(2)

    assert len(records) == 2
    assert driver.quit_calls == 1


def test_scrape_newest_stops_when_no_next_page(monkeypatch, scraped_records):
    driver = FakeDriver()
    monkeypatch.setattr(scrape, "_start_driver", lambda: driver)
    monkeypatch.setattr(scrape, "_load_page", lambda current, url: (current, url))
    monkeypatch.setattr(scrape, "extract_records", lambda soup: [scraped_records[0]])
    monkeypatch.setattr(scrape, "get_next", lambda soup, url: None)

    assert len(pull_data.scrape_newest(5)) == 1


# --- query_data.py --- #

@pytest.mark.parametrize(
    ("value", "column", "expected"),
    [(None, "average_gpa", "N/A"), (3, "difference", "+3"), (1234, "count", "1,234"),
     (Decimal("3.456"), "average_gpa", "3.46"), ("39.28%", "percent", "39.28%")],
)
def test_query_data_format_value(value, column, expected):
    assert query_data.format_value(value, column) == expected


def test_query_data_prints_every_question(db_connection, connect_to_test_db,
                                               monkeypatch, capsys):
    monkeypatch.setattr(query_data.psycopg, "connect", connect_to_test_db)

    assert query_data.main() == 0

    printed = capsys.readouterr().out
    assert all(f"Q{number}:" in printed for number in range(1, len(query_data.QUERIES) + 1))


def test_query_data_reports_db_failure(monkeypatch, capsys):
    def broken(**kwargs):
        raise psycopg.OperationalError("connection refused")

    monkeypatch.setattr(query_data.psycopg, "connect", broken)

    assert query_data.main() == 1
    assert "Query analysis failed" in capsys.readouterr().err
