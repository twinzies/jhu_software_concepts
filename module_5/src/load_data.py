"""Load cleaned Module 2 applicant JSON into PostgreSQL using DB_* environment variables."""

import argparse
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg import sql

import db
from sql_safety import APPLICANTS, MAX_LIMIT, clamp_limit

# The LLM cleaned data
DEFAULT_DATA = Path(__file__).resolve().with_name("llm_extend_applicant_data.json")

# Strings the grad cafe data uses for missing scores.
BLANKS = {"", "n/a", "na", "none", "null", "unknown"}


def as_text(value, key):
    """Trim text, treating only null and blank as missing."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key}: expected text, got {type(value).__name__}")
    return value.strip() or None


def as_number(value, key):
    """Parse a score, accepting Module 2's labelled form such as "GPA 3.40"."""
    if isinstance(value, str):
        value = re.sub(rf"^{re.escape(key)}\s*", "", value.strip(), flags=re.IGNORECASE)
        if value.lower() in BLANKS:
            return None
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key}: expected a number, got {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{key}: expected a finite number, got {value!r}")
    return number


def as_date(value, key):
    """Parses the date formats from the grad cafe json."""    
    value = as_text(value, key)
    if value is None:
        return None
    for date_format in ("%Y-%m-%d", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    raise ValueError(f"{key}: unrecognized date {value!r}")


# One row per column: database column, Module 2 JSON key, converter.
FIELDS = (
    ("program", "program", as_text),
    ("comments", "comments", as_text),
    ("date_added", "date_added", as_date),
    ("url", "url", as_text),
    ("status", "status", as_text),
    ("term", "term", as_text),
    ("us_or_international", "US/International", as_text),
    ("gpa", "GPA", as_number),
    ("gre", "GRE", as_number),
    ("gre_v", "GRE V", as_number),
    ("gre_aw", "GRE AW", as_number),
    ("degree", "Degree", as_text),
    ("llm_generated_program", "llm-generated-program", as_text),
    ("llm_generated_university", "llm-generated-university", as_text),
)
URL = [column for column, _, _ in FIELDS].index("url")

# Column names are quoted as identifiers and values are bound placeholders.
P_ID = sql.Identifier("p_id")
COLUMNS = sql.SQL(", ").join(sql.Identifier(column) for column, _, _ in FIELDS)
PLACEHOLDERS = sql.SQL(", ").join(sql.Placeholder() * len(FIELDS))

# Existing rows are read in pages, so no read runs without a LIMIT.
PAGE_SIZE = clamp_limit(MAX_LIMIT)

# Serializes concurrent loaders without table privileges beyond SELECT and INSERT.
LOADER_LOCK_ID = 5_000_001
LOCK_LOADERS = sql.SQL("SELECT pg_advisory_xact_lock(%(lock_id)s) LIMIT 1")

# Keyset pagination: each page starts after the last p_id the previous page returned.
SELECT_PAGE = sql.SQL("""
    SELECT {p_id}, {columns} FROM {table}
    WHERE {p_id} > %(after)s
    ORDER BY {p_id}
    LIMIT %(limit)s
""").format(p_id=P_ID, columns=COLUMNS, table=APPLICANTS)

INSERT_ROW = sql.SQL("INSERT INTO {table} ({columns}) VALUES ({values})").format(
    table=APPLICANTS, columns=COLUMNS, values=PLACEHOLDERS)


def to_row(record, position):
    """Convert one Module 2 record into a row of column values."""
    if not isinstance(record, dict):
        raise ValueError(f"Record {position}: expected a JSON object")
    try:
        return tuple(convert(record.get(key), key) for _, key, convert in FIELDS)
    except ValueError as exc:
        raise ValueError(f"Record {position}: {exc}") from exc


def read_records(path):
    """Read and validate the whole file before any database changes."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Input must be a JSON list of applicant objects")
    return [to_row(record, position) for position, record in enumerate(data, start=1)]


def dedup_key(row):
    """Identify a submission by its URL, or by the whole row when it has none."""
    return row[URL] or row


def existing_keys(cur):
    """Collect the dedup key of every stored row, one LIMITed page at a time."""
    seen, after = set(), 0
    while True:
        cur.execute(SELECT_PAGE, {"after": after, "limit": PAGE_SIZE})
        page = cur.fetchall()
        seen.update(dedup_key(tuple(values)) for _, *values in page)
        if len(page) < PAGE_SIZE:
            return seen
        after = page[-1][0]


def load_records(conn, rows):
    """Append unseen rows atomically and return (inserted, skipped)."""
    new_rows = []
    with conn.transaction(), conn.cursor() as cur:
        # Serialize concurrent loaders so that the check-then-insert below cannot race.
        cur.execute(LOCK_LOADERS, {"lock_id": LOADER_LOCK_ID})
        seen = existing_keys(cur)

        for row in rows:
            key = dedup_key(row)
            if key not in seen:
                seen.add(key)
                new_rows.append(row)

        if new_rows:
            # The statement is fixed; each row's values travel separately as parameters.
            cur.executemany(INSERT_ROW, new_rows)
    return len(new_rows), len(rows) - len(new_rows)


def main():
    """Load the cleaned JSON file into PostgreSQL; return 1 on failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", nargs="?", type=Path, default=DEFAULT_DATA,
                        help="Cleaned JSON path (default: Module 2 LLM-enriched data)")
    args = parser.parse_args()
    try:
        rows = read_records(args.data)
        with db.connect() as conn:
            inserted, skipped = load_records(conn, rows)
        print(f"Read {len(rows):,} records; inserted {inserted:,}; "
              f"skipped {skipped:,} existing/duplicate records.")
    except (OSError, ValueError, psycopg.Error) as exc:
        print(f"Load failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    main()
