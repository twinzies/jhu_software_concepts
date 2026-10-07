"""The eleven analysis questions as SQLAlchemy queries, to cross-check query_data.py.

SQLAlchemy binds every value as a parameter; run_queries adds a clamped LIMIT.
"""

# Part 6

# pylint can't see that SQLAlchemy's func.count is callable (a known false positive).
# pylint: disable=not-callable

import sys
from decimal import Decimal

from sqlalchemy import Numeric, and_, case, cast, func, or_, select
from sqlalchemy.exc import SQLAlchemyError

from models import Applicant, Session
from query_data import format_value
from sql_safety import DEFAULT_LIMIT, clamp_limit

# Questions 8 and 9 share the same term, admission status and degree filters.
accepted_phd = and_(
    Applicant.term.ilike("Fall 2026"),
    Applicant.status.ilike("Accepted"),
    Applicant.degree.ilike("PhD"),
)


def matches_university(column):
    """Recognize the four universities, including MIT as a whole word."""
    return or_(
        column.ilike("%Georgetown%"),
        column.ilike("%Massachusetts Institute of Technology%"),
        column.regexp_match(r"\mMIT\M", flags="i"),
        column.ilike("%Stanford%"),
        column.ilike("%Carnegie Mellon%"),
    )


def average(column):
    """Average the column, rounded to two decimal places."""
    return func.round(cast(func.avg(column), Numeric), 2)


def percentage(condition):
    """Percentage of rows matching the condition, formatted like "12.34%"."""
    return func.round(
        Decimal("100.0") * func.count().filter(condition) / func.nullif(func.count(), 0), 2
    ).concat("%")


original_match = and_(
    Applicant.program.ilike("%Computer Science%"),
    matches_university(Applicant.program),
)
llm_match = and_(
    Applicant.llm_generated_program.ilike("%Computer Science%"),
    matches_university(Applicant.llm_generated_university),
)

# Count each matching population independently for Question 9.
original_count = func.count().filter(original_match)
llm_count = func.count().filter(llm_match)

# Group name variants together for the original minimum-GPA question.
university = case(
    (Applicant.llm_generated_university.ilike("%Georgetown%"), "Georgetown University"),
    (
        or_(
            Applicant.llm_generated_university.ilike("%Massachusetts Institute of Technology%"),
            Applicant.llm_generated_university.ilike("MIT"),
        ),
        "Massachusetts Institute of Technology",
    ),
    (Applicant.llm_generated_university.ilike("%Stanford%"), "Stanford University"),
    (Applicant.llm_generated_university.ilike("%Carnegie Mellon%"), "Carnegie Mellon University"),
)

# The two reported nationalities Question 11 compares.
american = Applicant.us_or_international.ilike("American")
international = Applicant.us_or_international.ilike("International")

QUERIES = [
    # Question 1
    (1, select(func.count().label("fall_2026_count"))
        .select_from(Applicant)
        .where(func.lower(Applicant.term) == "fall 2026")),

    # Question 2
    (2, select(
            percentage(
                func.lower(Applicant.us_or_international) == "international"
            ).label("percent_international")
        )
        .select_from(Applicant)
        .where(
            Applicant.us_or_international.is_not(None),
            Applicant.us_or_international != "",
        )),

    # Question 3
    (3, select(
            average(Applicant.gpa).label("average_gpa"),
            average(Applicant.gre).label("average_gre_quantitative"),
            average(Applicant.gre_v).label("average_gre_verbal"),
            average(Applicant.gre_aw).label("average_gre_analytical_writing"),
        )),

    # Question 4
    (4, select(average(Applicant.gpa).label("average_gpa"))
        .where(
            func.lower(Applicant.term) == "fall 2026",
            func.lower(Applicant.us_or_international) == "american",
            Applicant.gpa.is_not(None),
        )),

    # Question 5
    (5, select(
            percentage(
                func.lower(Applicant.status) == "accepted"
            ).label("acceptance_percentage")
        )
        .select_from(Applicant)
        .where(
            func.lower(Applicant.term) == "fall 2025",
            Applicant.status.is_not(None),
            Applicant.status != "",
        )),

    # Question 6
    (6, select(average(Applicant.gpa).label("average_gpa"))
        .where(
            func.lower(Applicant.term) == "fall 2026",
            func.lower(Applicant.status) == "accepted",
            Applicant.gpa.is_not(None),
        )),

    # Question 7
    (7, select(func.count().label("jhu_cs_masters_count"))
        .select_from(Applicant)
        .where(
            or_(
                Applicant.program.ilike("%Johns Hopkins%"),
                Applicant.program.regexp_match(r"\mJHU\M", flags="i"),
            ),
            Applicant.program.ilike("%Computer Science%"),
            Applicant.degree.ilike("master%"),
        )),

    # Question 8
    (8, select(func.count().label("original_field_count"))
        .select_from(Applicant)
        .where(accepted_phd, original_match)),

    # Question 9
    (9, select(
            original_count.label("original_field_count"),
            llm_count.label("llm_field_count"),
            (llm_count - original_count).label("difference"),
        )
        .select_from(Applicant)
        .where(accepted_phd)),

    # Question 10 (my first question)
    (10, select(
            university.label("university"),
            func.min(Applicant.gpa).label("lowest_accepted_gpa"),
        )
        .where(accepted_phd, Applicant.gpa.is_not(None), university.is_not(None))
        .group_by(university)
        .order_by(university)),

    # Question 11 (my second question)
    (11, select(
            university.label("university"),
            func.min(Applicant.gpa).filter(american).label("lowest_american_gpa"),
            func.min(Applicant.gpa).filter(international).label("lowest_international_gpa"),
        )
        .where(
            accepted_phd,
            Applicant.gpa.is_not(None),
            university.is_not(None),
            or_(american, international),
        )
        .group_by(university)
        .order_by(university)),
]


def run_queries(session, limit=DEFAULT_LIMIT):
    """Return each question's result rows, with at most the clamped limit per question."""
    limit = clamp_limit(limit)
    results = {}
    for number, statement in QUERIES:
        results[number] = session.execute(statement.limit(limit)).mappings().all()
    return results


def main():
    """Print every answer on one snapshot; return 1 if the database fails."""
    try:
        with Session() as session:
            # Keep all results on one snapshot and prevent database changes.
            session.connection(execution_options={
                "isolation_level": "REPEATABLE READ",
                "postgresql_readonly": True,
            })
            results = run_queries(session)

        for number, rows in results.items():
            answers = []
            for row in rows:
                values = [format_value(value, column) for column, value in row.items()]
                answers.append(" | ".join(values))
            answer = "; ".join(answers) if answers else "N/A"
            print(f"Q{number}: {answer}")
    except SQLAlchemyError as error:
        print(f"ORM analysis failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    main()
