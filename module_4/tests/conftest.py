"""Shared fixtures that keep the suite off the network and off PostgreSQL."""

import json

import load_data
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
    def wire(scraper=None):
        recorder = PullRecorder(tmp_path / "pull_status.json")

        def load_records(connection, rows):
            recorder.loaded.append(rows)
            return len(rows), 0

        monkeypatch.setattr(pull_data, "scrape_newest",
                            scraper or (lambda pages: scraped_records))
        monkeypatch.setattr(pull_data, "STATUS_PATH", recorder.status_path)
        monkeypatch.setattr(scrape, "OUTPUT_PATH", tmp_path / "scraped_data.jsonl")
        monkeypatch.setattr(pull_data.psycopg, "connect", lambda **kwargs: FakeConnection())
        monkeypatch.setattr(load_data, "load_records", load_records)
        return recorder
    return wire
