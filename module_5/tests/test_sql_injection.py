"""Step 2: SQL injection defenses, composed statements, bound values and enforced LIMITs."""

import re

import pytest
from psycopg import sql

import clean
import load_data
import query_data
from sql_safety import APPLICANTS, MAX_LIMIT, MIN_LIMIT, clamp_limit

ATTACKS = [
    "1; DROP TABLE applicants; --",
    "' OR '1'='1",
    "1 UNION SELECT usename, passwd FROM pg_shadow --",
]

SELECTS = [*query_data.QUERIES, query_data.COUNT_APPLICANTS, load_data.SELECT_PAGE]


# --- LIMIT validation --- #

@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, MAX_LIMIT), ("", MAX_LIMIT), ("abc", MAX_LIMIT), ("50", 50), (" 7 ", 7),
     (3.9, 3), ("0", MIN_LIMIT), ("-5", MIN_LIMIT), ("101", MAX_LIMIT),
     ("1000000", MAX_LIMIT), ("9" * 5000, MAX_LIMIT)]
    + [(attack, MAX_LIMIT) for attack in ATTACKS],
)
def test_clamp_limit_keeps_every_input_in_range(value, expected):
    """Non-numbers fall back to the default; numbers are clamped to 1..100."""
    assert clamp_limit(value) == expected


# --- Statement construction --- #

@pytest.mark.parametrize("statement", SELECTS)
def test_every_select_is_composed_and_ends_with_a_bound_limit(statement):
    assert isinstance(statement, sql.Composable)
    assert re.search(r"LIMIT %\(limit\)s\s*$", statement.as_string(None))


@pytest.mark.parametrize("statement", query_data.QUERIES)
def test_filter_values_are_placeholders_not_sql_text(statement):
    text = statement.as_string(None)
    assert '"applicants"' in text, "the table name is quoted as an identifier"
    for value in query_data.FILTERS.values():
        assert f"'{value}'" not in text


def test_loader_statements_quote_columns_and_bind_values():
    insert = load_data.INSERT_ROW.as_string(None)
    assert insert.count("%s") == len(load_data.FIELDS)
    assert '"llm_generated_university"' in insert


# --- The Flask page's user-supplied limit --- #

@pytest.mark.web
@pytest.mark.parametrize(
    ("query", "expected"),
    [("", MAX_LIMIT), ("?limit=5", 5), ("?limit=0", MIN_LIMIT), ("?limit=-3", MIN_LIMIT),
     ("?limit=1000000", MAX_LIMIT), ("?limit=abc", MAX_LIMIT)]
    + [({"limit": attack}, MAX_LIMIT) for attack in ATTACKS],
)
def test_analysis_page_validates_the_limit(client, analysis_source, query, expected):
    """Malicious or oversized limits never reach the query layer unchanged."""
    if isinstance(query, dict):
        response = client.get("/analysis", query_string=query)
    else:
        response = client.get(f"/analysis{query}")

    assert response.status_code == 200
    assert analysis_source.limits[-1] == expected


# --- Against the test database --- #

def load(connection, records, **overrides):
    """Clean and load records, giving each the LLM fields the university questions read."""
    cleaned = clean.clean_data(records)
    for record, scraped in zip(cleaned, records):
        record["llm-generated-program"] = "Computer Science"
        record["llm-generated-university"] = scraped["university"]
        record.update(overrides)
    rows = [load_data.to_row(record, position) for position, record in enumerate(cleaned, 1)]
    result = load_data.load_records(connection, rows)
    connection.commit()
    return result


def table_count(connection):
    statement = sql.SQL("SELECT COUNT(*) FROM {} LIMIT 1").format(APPLICANTS)
    return connection.execute(statement).fetchone()[0]


@pytest.mark.db
def test_an_injected_filter_value_matches_nothing(db_connection, scraped_records, monkeypatch):
    """A tautology in a bound value is compared as text, so it returns no rows, not all rows."""
    load(db_connection, scraped_records)
    assert query_data.run_queries(db_connection)[1] == [{"fall_2026_count": 3}]

    monkeypatch.setitem(query_data.FILTERS, "fall_2026", "fall 2026' OR '1'='1")

    assert query_data.run_queries(db_connection)[1] == [{"fall_2026_count": 0}]


@pytest.mark.db
@pytest.mark.parametrize(("limit", "rows"), [(1, 1), (2, 2), ("999", 3), ("-1", 1),
                                             (ATTACKS[0], 3)])
def test_the_limit_caps_rows_per_question(db_connection, scraped_records, limit, rows):
    """Question 10 has one row per university; the clamped LIMIT caps how many come back."""
    load(db_connection, scraped_records)

    assert len(query_data.run_queries(db_connection, limit)[10]) == rows
    assert table_count(db_connection) == len(scraped_records)


@pytest.mark.db
def test_malicious_text_is_stored_verbatim(db_connection, scraped_records):
    """A classic payload in scraped data is just a value: stored as-is, table intact."""
    payload = "Robert'); DROP TABLE applicants; --"

    assert load(db_connection, scraped_records[:1], program=payload) == (1, 0)

    statement = sql.SQL("SELECT {} FROM {} LIMIT %s").format(
        sql.Identifier("program"), APPLICANTS)
    assert db_connection.execute(statement, [1]).fetchone()[0] == payload
    assert table_count(db_connection) == 1


@pytest.mark.db
def test_loader_reads_existing_rows_one_limited_page_at_a_time(
        db_connection, scraped_records, monkeypatch):
    """With one row per page the loader still sees every stored row before inserting."""
    load(db_connection, scraped_records)
    monkeypatch.setattr(load_data, "PAGE_SIZE", 1)

    assert load(db_connection, scraped_records) == (0, len(scraped_records))


@pytest.mark.integration
@pytest.mark.parametrize("attack", ATTACKS)
def test_page_survives_a_malicious_limit_against_the_database(
        end_to_end_app, db_connection, scraped_records, attack):
    load(db_connection, scraped_records)

    response = end_to_end_app.test_client().get("/analysis", query_string={"limit": attack})

    assert response.status_code == 200
    assert "Could not read the database" not in response.get_data(as_text=True)
    assert table_count(db_connection) == len(scraped_records)
