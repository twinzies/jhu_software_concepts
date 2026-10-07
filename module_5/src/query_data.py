"""Answer the eleven analysis questions with composed psycopg SQL.

Run from src/: python query_data.py. Connection settings come from DATABASE_URL
or the PG* environment variables.

Every statement is built once with psycopg's ``sql`` module: the table and
column names are quoted with ``sql.Identifier``, and every value, including
the LIMIT, is a named placeholder bound at execution time. No statement is
assembled from f-strings, ``+`` or ``.format()`` on raw SQL text.
"""

from decimal import Decimal
import os
import sys

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from sql_safety import APPLICANTS, DEFAULT_LIMIT, clamp_limit

# The values the questions filter on. They are bound as parameters, so they
# never become part of the SQL text, and ILIKE patterns keep their own % signs.
FILTERS = {
    "fall_2026": "fall 2026",
    "fall_2025": "fall 2025",
    "american": "american",
    "international": "international",
    "accepted": "accepted",
    "phd": "phd",
    "masters": "master%",
    "computer_science": "%Computer Science%",
    "johns_hopkins": "%Johns Hopkins%",
    "jhu_word": r"\mJHU\M",
    "georgetown": "%Georgetown%",
    "mit": "%Massachusetts Institute of Technology%",
    "mit_word": r"\mMIT\M",
    "mit_abbreviation": "MIT",
    "stanford": "%Stanford%",
    "carnegie_mellon": "%Carnegie Mellon%",
}


def _column(name):
    """Quote a column name as an identifier."""
    return sql.Identifier(name)


def _matches_university(column):
    """Recognize the four universities in the given column, with MIT as a whole word."""
    return sql.SQL("""(
        {column} ILIKE %(georgetown)s
        OR {column} ILIKE %(mit)s
        OR {column} ~* %(mit_word)s
        OR {column} ILIKE %(stanford)s
        OR {column} ILIKE %(carnegie_mellon)s
    )""").format(column=_column(column))


# Group name variants of the four universities under one name each.
UNIVERSITY_NAME = sql.SQL("""CASE
        WHEN {column} ILIKE %(georgetown)s THEN 'Georgetown University'
        WHEN {column} ILIKE %(mit)s OR {column} ILIKE %(mit_abbreviation)s
            THEN 'Massachusetts Institute of Technology'
        WHEN {column} ILIKE %(stanford)s THEN 'Stanford University'
        WHEN {column} ILIKE %(carnegie_mellon)s THEN 'Carnegie Mellon University'
    END""").format(column=_column("llm_generated_university"))

# Questions 8 to 11 share the same term, admission status and degree filters.
ACCEPTED_PHD = sql.SQL(
    "term ILIKE %(fall_2026)s AND status ILIKE %(accepted)s AND degree ILIKE %(phd)s"
)

# The pieces every template may use. LIMIT is always a bound placeholder.
FRAGMENTS = {
    "table": APPLICANTS,
    "limit": sql.Placeholder("limit"),
    "accepted_phd": ACCEPTED_PHD,
    "university_name": UNIVERSITY_NAME,
    "original_university": _matches_university("program"),
    "llm_university": _matches_university("llm_generated_university"),
}


def compose(template):
    """Build a statement from a SQL template and the shared, safely quoted fragments."""
    return sql.SQL(template).format(**FRAGMENTS)


# Queries are listed in question order; results print as Q1, Q2, and so on.
QUERIES = [compose(template) for template in (
    # Question 1: Number of applicants for Fall 2026.
    """
    SELECT COUNT(*) AS fall_2026_count
    FROM {table}
    WHERE LOWER(term) = %(fall_2026)s
    LIMIT {limit}
    """,

    # Question 2: International percentage among reported nationalities.
    """
    SELECT ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE LOWER(us_or_international) = %(international)s
        ) / NULLIF(COUNT(*), 0), 2
    ) || '%%' AS percent_international
    FROM {table}
    WHERE us_or_international IS NOT NULL
      AND us_or_international <> ''
    LIMIT {limit}
    """,

    # Question 3: Average each reported GPA/GRE metric independently.
    """
    SELECT
        ROUND(AVG(gpa)::numeric, 2) AS average_gpa,
        ROUND(AVG(gre)::numeric, 2) AS average_gre_quantitative,
        ROUND(AVG(gre_v)::numeric, 2) AS average_gre_verbal,
        ROUND(AVG(gre_aw)::numeric, 2) AS average_gre_analytical_writing
    FROM {table}
    LIMIT {limit}
    """,

    # Question 4: Average GPA of American applicants for Fall 2026.
    """
    SELECT ROUND(AVG(gpa)::numeric, 2) AS average_gpa
    FROM {table}
    WHERE LOWER(term) = %(fall_2026)s
      AND LOWER(us_or_international) = %(american)s
      AND gpa IS NOT NULL
    LIMIT {limit}
    """,

    # Question 5: Fall 2025 acceptance percentage, excluding unreported status.
    # The assignment uses all Fall 2025 entries; this keeps your requested exclusion.
    """
    SELECT ROUND(
        100.0 * COUNT(*) FILTER (WHERE LOWER(status) = %(accepted)s)
        / NULLIF(COUNT(*), 0), 2
    ) || '%%' AS acceptance_percentage
    FROM {table}
    WHERE LOWER(term) = %(fall_2025)s
      AND status IS NOT NULL
      AND status <> ''
    LIMIT {limit}
    """,

    # Question 6: Average GPA of accepted Fall 2026 applicants.
    """
    SELECT ROUND(AVG(gpa)::numeric, 2) AS average_gpa
    FROM {table}
    WHERE LOWER(term) = %(fall_2026)s
      AND LOWER(status) = %(accepted)s
      AND gpa IS NOT NULL
    LIMIT {limit}
    """,

    # Question 7: Johns Hopkins Computer Science master's entries (original fields).
    # Whole-word JHU matching recognizes the university abbreviation.
    """
    SELECT COUNT(*) AS jhu_cs_masters_count
    FROM {table}
    WHERE (program ILIKE %(johns_hopkins)s OR program ~* %(jhu_word)s)
      AND program ILIKE %(computer_science)s
      AND degree ILIKE %(masters)s
    LIMIT {limit}
    """,

    # Question 8: Fall 2026 CS PhD acceptances at the four universities (original fields).
    # Whole-word MIT matching avoids accidentally matching RMIT.
    """
    SELECT COUNT(*) AS original_field_count
    FROM {table}
    WHERE {accepted_phd}
      AND program ILIKE %(computer_science)s
      AND {original_university}
    LIMIT {limit}
    """,

    # Question 9: Compare the original and LLM-field counts; subtract original from LLM.
    """
    WITH counts AS (
        SELECT
            COUNT(*) FILTER (
                WHERE program ILIKE %(computer_science)s AND {original_university}
            ) AS original_field_count,
            COUNT(*) FILTER (
                WHERE llm_generated_program ILIKE %(computer_science)s AND {llm_university}
            ) AS llm_field_count
        FROM {table}
        WHERE {accepted_phd}
    )
    SELECT original_field_count, llm_field_count,
           llm_field_count - original_field_count AS difference
    FROM counts
    LIMIT {limit}
    """,

    # Question 10 (my first question): Lowest accepted PhD GPA at each university.
    """
    WITH admitted AS (
        SELECT {university_name} AS university, gpa
        FROM {table}
        WHERE {accepted_phd} AND gpa IS NOT NULL
    )
    SELECT university, MIN(gpa) AS lowest_accepted_gpa
    FROM admitted
    WHERE university IS NOT NULL
    GROUP BY university
    ORDER BY university
    LIMIT {limit}
    """,

    # Question 11 (my second question): Lowest GPA by university and nationality.
    """
    WITH admitted AS (
        SELECT {university_name} AS university, us_or_international, gpa
        FROM {table}
        WHERE {accepted_phd}
          AND gpa IS NOT NULL
          AND (us_or_international ILIKE %(american)s
               OR us_or_international ILIKE %(international)s)
    )
    SELECT university,
        MIN(gpa) FILTER (WHERE us_or_international ILIKE %(american)s)
            AS lowest_american_gpa,
        MIN(gpa) FILTER (WHERE us_or_international ILIKE %(international)s)
            AS lowest_international_gpa
    FROM admitted
    WHERE university IS NOT NULL
    GROUP BY university
    ORDER BY university
    LIMIT {limit}
    """,
)]

# The total row count shown on the Flask page; one row, but still limited.
COUNT_APPLICANTS = compose("SELECT COUNT(*) AS total FROM {table} LIMIT {limit}")

QUESTIONS = {
    1: "How many entries are from applicants who applied for Fall 2026?",
    2: "Among entries that provide a nationality, what percentage are international students?",
    3: "What are the average GPA, GRE Quantitative, GRE Verbal and GRE Analytical Writing scores?",
    4: "What is the average GPA of American applicants who applied for Fall 2026?",
    5: "What percentage of Fall 2025 entries are acceptances?",
    6: "What is the average GPA of accepted applicants who applied for Fall 2026?",
    7: "How many entries are Johns Hopkins master's applications in Computer Science?",
    8: "How many Fall 2026 entries are PhD Computer Science acceptances at Georgetown, "
       "MIT, Stanford or Carnegie Mellon?",
    9: "Question 8 again, using the LLM-generated program and university fields instead.",
    10: "What was the lowest GPA accepted to a doctoral program at those four "
        "universities for Fall 2026?",
    11: "At those same universities, what was the lowest accepted GPA for American "
        "and for international applicants?",
}


def connect(url=None):
    """Open a read-only, single-snapshot connection from DATABASE_URL or the PG* variables."""
    if url is None:
        url = os.environ.get("DATABASE_URL", "")
    # SQLAlchemy-style URLs name the driver; libpq expects the plain scheme.
    url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    connection = psycopg.connect(conninfo=url, connect_timeout=10)
    # Keep every answer on the same snapshot and prevent database changes.
    connection.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
    connection.read_only = True
    return connection


def query_params(limit):
    """Bind the filter values and the clamped LIMIT for one run."""
    return {**FILTERS, "limit": clamp_limit(limit)}


def run_queries(connection, limit=DEFAULT_LIMIT):
    """Execute each composed statement with bound parameters; return rows keyed by question."""
    params = query_params(limit)
    results = {}
    with connection.cursor(row_factory=dict_row) as cursor:
        for number, statement in enumerate(QUERIES, start=1):
            cursor.execute(statement, params)
            results[number] = cursor.fetchall()
    return results


def count_applicants(connection, limit=DEFAULT_LIMIT):
    """Return how many rows the applicants table holds."""
    with connection.cursor() as cursor:
        cursor.execute(COUNT_APPLICANTS, {"limit": clamp_limit(limit)})
        return cursor.fetchone()[0]


def format_value(value, column):
    """Display missing values, whole-number counts and two-decimal scores."""
    if value is None:
        return "N/A"
    if column == "difference":
        return f"{value:+d}"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, (float, Decimal)):
        return f"{value:.2f}"
    return str(value)


def format_answer(rows):
    """One line per question; multiple result rows are separated with semicolons."""
    answers = [" | ".join(format_value(value, column) for column, value in row.items())
               for row in rows]
    return "; ".join(answers) if answers else "N/A"


def main():
    """Print every answer on one snapshot; return 1 if the database fails."""
    try:
        with connect() as connection:
            results = run_queries(connection)
    except psycopg.Error as error:
        print(f"Query analysis failed: {error}", file=sys.stderr)
        return 1
    for number, rows in results.items():
        print(f"Q{number}: {format_answer(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
