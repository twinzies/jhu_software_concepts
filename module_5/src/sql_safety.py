"""Shared SQL safety rules: the table identifier and the enforced LIMIT range.

Every statement in the project is composed with psycopg's ``sql`` module and
carries a LIMIT. Limits arrive here first, so no caller can request more than
MAX_LIMIT rows at once, whatever the input.
"""

from psycopg import sql

# Identifiers are quoted by psycopg, never pasted into SQL text.
APPLICANTS = sql.Identifier("applicants")

MIN_LIMIT = 1
MAX_LIMIT = 100
DEFAULT_LIMIT = MAX_LIMIT


def clamp_limit(value, default=DEFAULT_LIMIT):
    """Return value as an int within MIN_LIMIT..MAX_LIMIT, or default if it isn't a number.

    Untrusted input such as "5; DROP TABLE applicants" or a huge number never
    reaches the database: it becomes the default or the nearest bound.
    """
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(MIN_LIMIT, min(MAX_LIMIT, number))
