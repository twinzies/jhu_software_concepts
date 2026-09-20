# Part 6

from decimal import Decimal
import sys

from sqlalchemy import Numeric, and_, case, cast, func, or_, select
from sqlalchemy.exc import SQLAlchemyError

from models import Applicant, Session


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

QUERIES = [
    # Question 1
    (1, select(func.count().label("fall_2026_count"))
        .select_from(Applicant)
        .where(func.lower(Applicant.term) == "fall 2026")),

    # Question 4
    (4, select(func.round(cast(func.avg(Applicant.gpa), Numeric), 2).label("average_gpa"))
        .where(
            func.lower(Applicant.term) == "fall 2026",
            func.lower(Applicant.us_or_international) == "american",
            Applicant.gpa.is_not(None),
        )),

    # Question 5
    (5, select(
            func.round(
                Decimal("100.0")
                * func.count().filter(func.lower(Applicant.status) == "accepted")
                / func.nullif(func.count(), 0),
                2,
            ).concat("%").label("acceptance_percentage")
        )
        .select_from(Applicant)
        .where(
            func.lower(Applicant.term) == "fall 2025",
            Applicant.status.is_not(None),
            Applicant.status != "",
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
]


def run_queries(session):
    """Return each question's result rows for console output or Flask."""
    results = {}
    for number, statement in QUERIES:
        results[number] = session.execute(statement).mappings().all()
    return results


def format_value(value, column):
    """Use the same formatting as query_data.py."""
    if value is None:
        return "N/A"
    if column == "difference":
        return f"{value:+d}"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, (float, Decimal)):
        return f"{value:.2f}"
    return str(value)


def main():
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
