"""Task 4: Test rows written by a pull, uniqueness on repeat pulls, and the query function."""

import clean
import load_data
import pytest
from conftest import REQUIRED_COLUMNS
from orm_queries import run_queries

pytestmark = pytest.mark.db

# The column keys for each question in the analysis template.
EXPECTED_KEYS = {
    1: {"fall_2026_count"},
    2: {"percent_international"},
    3: {"average_gpa", "average_gre_quantitative", "average_gre_verbal",
        "average_gre_analytical_writing"},
    4: {"average_gpa"},
    5: {"acceptance_percentage"},
    6: {"average_gpa"},
    7: {"jhu_cs_masters_count"},
    8: {"original_field_count"},
    9: {"original_field_count", "llm_field_count", "difference"},
    10: {"university", "lowest_accepted_gpa"},
    11: {"university", "lowest_american_gpa", "lowest_international_gpa"},
}

def count(connection):
    return connection.execute("SELECT count(*) FROM applicants").fetchone()[0]


def rows_from(records):
    """Run fake scraper records through the real clean and to_row steps."""
    return [load_data.to_row(record, position)
            for position, record in enumerate(clean.clean_data(records), start=1)]


def test_pull_inserts_rows_into_an_empty_table(loading_app, db_connection, scraped_records):
    """4a: empty before, and afterwards every required field is populated."""
    assert count(db_connection) == 0

    assert loading_app.test_client().post("/pull-data").status_code in (200, 202)

    columns = ", ".join(REQUIRED_COLUMNS)
    written = db_connection.execute(f"SELECT {columns} FROM applicants").fetchall()
    assert len(written) == len(scraped_records)
    for row in written:
        assert all(value is not None for value in row)


def test_second_pull_adds_no_duplicate_rows(loading_app, db_connection, scraped_records):
    """4b: pulling the same data twice leaves the row count unchanged."""
    client = loading_app.test_client()
    client.post("/pull-data")
    after_first = count(db_connection)

    client.post("/pull-data")

    assert after_first == len(scraped_records)
    assert count(db_connection) == after_first


def test_load_records_skips_rows_already_in_the_table(db_connection, scraped_records):
    """4b at the database layer: the loader itself refuses rows it has seen."""
    rows = rows_from(scraped_records)
    inserted, skipped = load_data.load_records(db_connection, rows)
    assert (inserted, skipped) == (len(rows), 0)

    assert load_data.load_records(db_connection, rows) == (0, len(rows))
    assert count(db_connection) == len(rows)

def test_query_function_returns_expected_keys(db_connection, db_session, scraped_records):
    """4c: run_queries returns a dict of rows keyed by the template's column names."""
    load_data.load_records(db_connection, rows_from(scraped_records))
    db_connection.commit()

    results = run_queries(db_session)

    assert set(results) == set(EXPECTED_KEYS)
    for number, rows in results.items():
        for row in rows:
            assert set(row.keys()) == EXPECTED_KEYS[number]
