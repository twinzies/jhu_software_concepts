"""Shared fixtures that keep the suite off the network and off PostgreSQL."""

import pytest
from app import build_blocks, create_app
from bs4 import BeautifulSoup

# Fake query rows, run through the real build_blocks so the shape cannot drift.
FAKE_RESULTS = {
    1: [{"fall_2026_count": 1234}],
    2: [{"percent_international": "39.28%"}],
    3: [{"average_gpa": 3.5, "average_gre_quantitative": 161.0,
         "average_gre_verbal": 157.0, "average_gre_analytical_writing": 4.0}],
    10: [{"university": "Carnegie Mellon University", "lowest_accepted_gpa": 3.33},
         {"university": "Stanford University", "lowest_accepted_gpa": 3.6}],
    11: [],
}

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
    return dict(FAKE_RESULTS)


@pytest.fixture
def analysis_source(fake_results):
    """A drop-in for database_analysis that never opens a session."""
    def source():
        return build_blocks(fake_results), FAKE_TOTAL
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
