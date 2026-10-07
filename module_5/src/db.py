"""PostgreSQL connections configuration through environment variables."""

import os

import psycopg

# libpq keyword -> environment variable. Unset ones fall back to libpq defaults (PG*).
ENV_VARS = {
    "host": "DB_HOST",
    "port": "DB_PORT",
    "dbname": "DB_NAME",
    "user": "DB_USER",
    "password": "DB_PASSWORD",
}


def settings():
    """Return connection keywords for the DB_* variables that are set."""
    return {key: os.environ[name] for key, name in ENV_VARS.items() if os.environ.get(name)}


def connect(**options):
    """Open a connection using the DB_* settings."""
    return psycopg.connect(**settings(), connect_timeout=10, **options)
