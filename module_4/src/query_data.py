"""Answer the eleven analysis questions in raw SQL and print them.

Run from src/: python query_data.py. Connection settings come from DATABASE_URL
or the PG* environment variables.
"""

from decimal import Decimal
import sys

import psycopg


# Queries are listed in question order; results print as Q1, Q2, and so on.
QUERIES = [
    # Question 1: Number of applicants for Fall 2026.
    r"""
    SELECT COUNT(*) AS fall_2026_count
    FROM applicants
    WHERE LOWER(term) = 'fall 2026';
    """,

    # Question 2: International percentage among reported nationalities.
    r"""
    SELECT ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE LOWER(us_or_international) = 'international'
        ) / NULLIF(COUNT(*), 0), 2
    ) || '%' AS percent_international
    FROM applicants
    WHERE us_or_international IS NOT NULL
      AND us_or_international <> '';
    """,

    # Question 3: Average each reported GPA/GRE metric independently.
    r"""
    SELECT
        ROUND(AVG(gpa)::numeric, 2) AS average_gpa,
        ROUND(AVG(gre)::numeric, 2) AS average_gre_quantitative,
        ROUND(AVG(gre_v)::numeric, 2) AS average_gre_verbal,
        ROUND(AVG(gre_aw)::numeric, 2) AS average_gre_analytical_writing
    FROM applicants;
    """,

    # Question 4: Average GPA of American applicants for Fall 2026.
    r"""
    SELECT ROUND(AVG(gpa)::numeric, 2) AS average_gpa
    FROM applicants
    WHERE LOWER(term) = 'fall 2026'
      AND LOWER(us_or_international) = 'american'
      AND gpa IS NOT NULL;
    """,

    # Question 5: Fall 2025 acceptance percentage, excluding unreported status.
    # The assignment uses all Fall 2025 entries; this keeps your requested exclusion.
    r"""
    SELECT ROUND(
        100.0 * COUNT(*) FILTER (WHERE LOWER(status) = 'accepted')
        / NULLIF(COUNT(*), 0), 2
    ) || '%' AS acceptance_percentage
    FROM applicants
    WHERE LOWER(term) = 'fall 2025'
      AND status IS NOT NULL
      AND status <> '';
    """,

    # Question 6: Average GPA of accepted Fall 2026 applicants.
    r"""
    SELECT ROUND(AVG(gpa)::numeric, 2) AS average_gpa
    FROM applicants
    WHERE LOWER(term) = 'fall 2026'
      AND LOWER(status) = 'accepted'
      AND gpa IS NOT NULL;
    """,

    # Question 7: Johns Hopkins Computer Science master's entries (original fields).
    # Whole-word JHU matching recognizes the university abbreviation.
    r"""
    SELECT COUNT(*) AS jhu_cs_masters_count
    FROM applicants
    WHERE (
        program ILIKE '%Johns Hopkins%'
        OR program ~* '\mJHU\M'
    )
      AND program ILIKE '%Computer Science%'
      AND degree ILIKE 'master%';
    """,

    # Question 8: Fall 2026 CS PhD acceptances at the four universities (original fields).
    # Whole-word MIT matching avoids accidentally matching RMIT.
    r"""
    SELECT COUNT(*) AS original_field_count
    FROM applicants
    WHERE term ILIKE 'Fall 2026'
      AND status ILIKE 'Accepted'
      AND degree ILIKE 'PhD'
      AND program ILIKE '%Computer Science%'
      AND (
          program ILIKE '%Georgetown%'
          OR program ILIKE '%Massachusetts Institute of Technology%'
          OR program ~* '\mMIT\M'
          OR program ILIKE '%Stanford%'
          OR program ILIKE '%Carnegie Mellon%'
      );
    """,

    # Question 9: Compare the original and LLM-field counts; subtract original from LLM.
    r"""
    WITH eligible AS (
        SELECT program, llm_generated_program, llm_generated_university
        FROM applicants
        WHERE term ILIKE 'Fall 2026'
          AND status ILIKE 'Accepted'
          AND degree ILIKE 'PhD'
    ), counts AS (
        SELECT
            COUNT(*) FILTER (
                WHERE program ILIKE '%Computer Science%'
                  AND (
                      program ILIKE '%Georgetown%'
                      OR program ILIKE '%Massachusetts Institute of Technology%'
                      OR program ~* '\mMIT\M'
                      OR program ILIKE '%Stanford%'
                      OR program ILIKE '%Carnegie Mellon%'
                  )
            ) AS original_field_count,
            COUNT(*) FILTER (
                WHERE llm_generated_program ILIKE '%Computer Science%'
                  AND (
                      llm_generated_university ILIKE '%Georgetown%'
                      OR llm_generated_university ILIKE '%Massachusetts Institute of Technology%'
                      OR llm_generated_university ~* '\mMIT\M'
                      OR llm_generated_university ILIKE '%Stanford%'
                      OR llm_generated_university ILIKE '%Carnegie Mellon%'
                  )
            ) AS llm_field_count
        FROM eligible
    )
    SELECT original_field_count, llm_field_count,
           llm_field_count - original_field_count AS difference
    FROM counts;
    """,

    # Question 10 (my first question): Lowest accepted PhD GPA at each university.
    r"""
    WITH admitted AS (
        SELECT
            CASE
                WHEN llm_generated_university ILIKE '%Georgetown%'
                    THEN 'Georgetown University'
                WHEN llm_generated_university ILIKE '%Massachusetts Institute of Technology%'
                  OR llm_generated_university ILIKE 'MIT'
                    THEN 'Massachusetts Institute of Technology'
                WHEN llm_generated_university ILIKE '%Stanford%'
                    THEN 'Stanford University'
                WHEN llm_generated_university ILIKE '%Carnegie Mellon%'
                    THEN 'Carnegie Mellon University'
            END AS university,
            gpa
        FROM applicants
        WHERE status ILIKE 'Accepted'
          AND term ILIKE 'Fall 2026'
          AND degree ILIKE 'PhD'
          AND gpa IS NOT NULL
    )
    SELECT university, MIN(gpa) AS lowest_accepted_gpa
    FROM admitted
    WHERE university IS NOT NULL
    GROUP BY university
    ORDER BY university;
    """,

    # Question 11 (my second question): Lowest GPA by university and nationality.
    r"""
    WITH admitted AS (
        SELECT
            CASE
                WHEN llm_generated_university ILIKE '%Georgetown%'
                    THEN 'Georgetown University'
                WHEN llm_generated_university ILIKE '%Massachusetts Institute of Technology%'
                  OR llm_generated_university ILIKE 'MIT'
                    THEN 'Massachusetts Institute of Technology'
                WHEN llm_generated_university ILIKE '%Stanford%'
                    THEN 'Stanford University'
                WHEN llm_generated_university ILIKE '%Carnegie Mellon%'
                    THEN 'Carnegie Mellon University'
            END AS university,
            us_or_international, gpa
        FROM applicants
        WHERE status ILIKE 'Accepted'
          AND term ILIKE 'Fall 2026'
          AND degree ILIKE 'PhD'
          AND gpa IS NOT NULL
          AND (us_or_international ILIKE 'American'
               OR us_or_international ILIKE 'International')
    )
    SELECT university,
        MIN(gpa) FILTER (WHERE us_or_international ILIKE 'American')
            AS lowest_american_gpa,
        MIN(gpa) FILTER (WHERE us_or_international ILIKE 'International')
            AS lowest_international_gpa
    FROM admitted
    WHERE university IS NOT NULL
    GROUP BY university
    ORDER BY university;
    """,

]


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


def print_result(number, cursor):
    """Print one line per question; separate multiple result rows with semicolons."""
    columns = [column.name for column in cursor.description]
    results = []
    for row in cursor.fetchall():
        values = [format_value(value, column) for column, value in zip(columns, row)]
        results.append(" | ".join(values))
    answer = "; ".join(results) if results else "N/A"
    print(f"Q{number}: {answer}")


def main():
    try:
        with psycopg.connect(connect_timeout=10) as connection:
            with connection.cursor() as cursor:
                # Keep every answer on the same snapshot and prevent database changes.
                cursor.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
                )
                for number, sql in enumerate(QUERIES, start=1):
                    cursor.execute(sql)
                    print_result(number, cursor)
    except psycopg.Error as error:
        print(f"Query analysis failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
