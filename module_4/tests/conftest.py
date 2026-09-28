"""Shared fixtures that keep the suite off the network and off PostgreSQL."""

import getpass
import json
import os
from urllib.parse import urlsplit, urlunsplit
import load_data
import models
import psycopg
import pull_data
import pytest
import scrape
from bs4 import BeautifulSoup
from app import build_blocks, create_app

FAKE_TOTAL = 1234


class FakeProcess:
    """Stand-in for subprocess.Popen; tests set returncode instead of sleeping."""

    def __init__(self, returncode=0):
        self.returncode = returncode
        self.polls = 0

    def poll(self):
        self.polls += 1
        return self.returncode


@pytest.fixture
def fake_results():
    """The raw query results the fake analysis source is built from."""
    return {
    1: [{"fall_2026_count": 1234}],
    2: [{"percent_international": "39.28%"}],
    3: [{"average_gpa": 3.5, "average_gre_quantitative": 161.0,
         "average_gre_verbal": 157.0, "average_gre_analytical_writing": 4.0}],
    10: [{"university": "Carnegie Mellon University", "lowest_accepted_gpa": 3.33},
         {"university": "Stanford University", "lowest_accepted_gpa": 3.6}],
    11: [],
    }


@pytest.fixture
def analysis_source(fake_results):
    """A drop-in for database_analysis that never opens a session and counts its calls."""
    def source():
        source.calls += 1
        return build_blocks(fake_results), FAKE_TOTAL
    source.calls = 0
    return source


@pytest.fixture
def pull_runner():
    """A runner that starts an already-finished pull, so the app is never busy."""
    return lambda: FakeProcess(returncode=0)


@pytest.fixture
def app(tmp_path, analysis_source, pull_runner):
    """A testable app with no database, no subprocess and a status file in tmp_path."""
    return create_app(
        {
            "TESTING": True,
            "PULL_STATUS_PATH": str(tmp_path / "pull_status.json"),
        },
        analysis_source=analysis_source,
        pull_runner=pull_runner,
    )


@pytest.fixture
def client(app):
    """Flask's test client, used instead of driving a real browser."""
    return app.test_client()


@pytest.fixture
def page(client):
    """The parsed GET /analysis response, for tests that only read the HTML."""
    response = client.get("/analysis")
    return BeautifulSoup(response.get_data(as_text=True), "html.parser")


@pytest.fixture
def busy(app):
    """Put the app into the pull-in-progress state, with no timing involved."""
    def go():
        app.extensions["pull_state"].process = FakeProcess(returncode=None)
        return app.extensions["pull_state"]
    return go


@pytest.fixture
def scraped_records():
    """Several fake scraper records, carrying the keys clean._clean_record reads."""
    return [
        {
            "program": "Computer Science", "university": university,
            "comments": "", "date_added": "2026-01-15",
            "url": f"https://example.test/result/{number}",
            "status_raw": "Accepted on Jan 09", "term": "Fall 2026",
            "US/International": "International",
            "GRE": None, "GRE V": None, "GRE AW": None, "GPA": gpa,
            "degree": "PhD", "details_raw": "",
        }
        for number, university, gpa in [
            (1, "Stanford University", "3.90"),
            (2, "Carnegie Mellon University", "3.75"),
            (3, "Massachusetts Institute of Technology", "3.60"),
        ]
    ]


class FakeConnection:
    """Context manager standing in for psycopg.connect, so no database is opened."""

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class PullRecorder:
    """What a faked pull handed to the loader, and where its status file landed."""

    def __init__(self, status_path):
        self.status_path = status_path
        self.loaded = []

    @property
    def rows(self):
        """Every row the loader received, flattened across calls."""
        return [row for batch in self.loaded for row in batch]

    def status(self):
        return json.loads(self.status_path.read_text(encoding="utf-8"))


@pytest.fixture
def pull_pipeline(monkeypatch, tmp_path, scraped_records):
    """Wire pull_data.main() to fake scrape/database stages and record the loader's rows."""
    def wire(scraper=None, connect=None, loader=None):
        """loader defaults to a counting stub; pass load_data.load_records to really write."""
        recorder = PullRecorder(tmp_path / "pull_status.json")
        write = loader or (lambda connection, rows: (len(rows), 0))

        def load_records(connection, rows):
            recorder.loaded.append(rows)
            return write(connection, rows)

        monkeypatch.setattr(pull_data, "scrape_newest",
                            scraper or (lambda pages: scraped_records))
        monkeypatch.setattr(pull_data, "STATUS_PATH", recorder.status_path)
        monkeypatch.setattr(scrape, "OUTPUT_PATH", tmp_path / "scraped_data.jsonl")
        monkeypatch.setattr(pull_data.psycopg, "connect",
                            connect or (lambda **kwargs: FakeConnection()))
        monkeypatch.setattr(load_data, "load_records", load_records)
        return recorder
    return wire


TEST_DB_NAME = "module_4_test"

# Required in the Module 3 schema: every scraped submission carries these.
REQUIRED_COLUMNS = ("program", "date_added", "url", "status", "term",
                    "us_or_international", "degree")


def _with_scheme(url, scheme):
    return urlunsplit(urlsplit(url)._replace(scheme=scheme))


def _test_database_url():
    """A dedicated test database, derived from the environment but never the app's own."""
    if os.environ.get("TEST_DATABASE_URL"):
        return _with_scheme(os.environ["TEST_DATABASE_URL"], "postgresql")
    configured = os.environ.get("DATABASE_URL")
    if configured:
        return _with_scheme(
            urlunsplit(urlsplit(configured)._replace(path=f"/{TEST_DB_NAME}")), "postgresql")
    user = os.environ.get("PGUSER") or getpass.getuser()
    host = os.environ.get("PGHOST", "localhost")
    port = os.environ.get("PGPORT", "5432")
    return f"postgresql://{user}@{host}:{port}/{TEST_DB_NAME}"


@pytest.fixture(scope="session")
def db_url():
    """Create the test database if needed, or skip when PostgreSQL is unreachable."""
    url = _test_database_url()
    admin = urlunsplit(urlsplit(url)._replace(path="/postgres"))
    try:
        with psycopg.connect(admin, connect_timeout=5, autocommit=True) as connection:
            exists = connection.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", [TEST_DB_NAME]).fetchone()
            if not exists:
                connection.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    except psycopg.Error as error:
        pytest.skip(f"PostgreSQL unavailable: {error}")
    return url


@pytest.fixture
def db_connection(db_url):
    """An empty applicants table on the test database, for one test."""
    with psycopg.connect(db_url) as connection:
        connection.execute(load_data.CREATE_TABLE)
        connection.execute("TRUNCATE applicants RESTART IDENTITY")
        connection.commit()
        yield connection


@pytest.fixture
def db_session(db_url):
    """A SQLAlchemy session on the test database, restoring the app's binding after."""
    models.configure(_with_scheme(db_url, "postgresql+psycopg"))
    with models.Session() as session:
        yield session
    models.configure(models.database_url())


@pytest.fixture
def loading_app(tmp_path, analysis_source, pull_pipeline, db_url, db_connection):
    """An app whose Pull Data button runs the real loader against the test database."""
    # Captured before pull_pipeline patches the shared psycopg.connect attribute.
    connect = psycopg.connect
    pull_pipeline(connect=lambda **kwargs: connect(db_url),
                  loader=load_data.load_records)

    def runner():
        pull_data.main()
        return FakeProcess(returncode=0)

    return create_app(
        {"TESTING": True, "PULL_STATUS_PATH": str(tmp_path / "pull_status.json")},
        analysis_source=analysis_source,
        pull_runner=runner,
    )
