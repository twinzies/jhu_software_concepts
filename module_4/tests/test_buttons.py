"""Task 2: Pull Data and Update Analysis endpoints, and busy-state gating."""

import subprocess

import pytest
from conftest import FakeProcess

import pull_data
from app import create_app, spawn_pull

# Add marker to every test in this module.
pytestmark = pytest.mark.buttons

HTML = {"Accept": "text/html"}


# --- 2a. POST /pull-data --- #

def test_pull_data_starts_a_pull_when_not_busy(app, client):
    response = client.post("/pull-data")

    assert response.status_code in (200, 202)
    assert response.get_json() == {"ok": True}
    assert isinstance(app.extensions["pull_state"].process, FakeProcess)


def test_pull_triggers_loader_with_scraped_rows(pull_pipeline, scraped_records):
    recorder = pull_pipeline()

    assert pull_data.main() == 0
    assert [row[3] for row in recorder.rows] == [record["url"] for record in scraped_records]
    assert recorder.status()["state"] == "finished"


# --- 2b. POST /update-analysis --- #

def test_update_analysis_returns_ok_when_not_busy(client):
    """2b-i."""
    response = client.post("/update-analysis")

    assert response.status_code == 200
    assert response.get_json() == {"ok": True}


def test_update_analysis_refreshes_the_page(client, analysis_source):
    """The button re-runs the analysis."""
    before = analysis_source.calls
    response = client.post("/update-analysis", headers=HTML, follow_redirects=True)

    assert response.status_code == 200
    assert analysis_source.calls > before


# --- 2c. Busy gating --- #

def test_update_analysis_is_gated_when_busy(client, busy, analysis_source):
    busy()
    before = analysis_source.calls
    response = client.post("/update-analysis")

    assert response.status_code == 409
    assert response.get_json() == {"busy": True}
    assert analysis_source.calls == before


def test_pull_data_is_gated_when_busy(app, client, busy):
    running = busy().process
    response = client.post("/pull-data")

    assert response.status_code == 409
    assert response.get_json() == {"busy": True}
    assert app.extensions["pull_state"].process is running


def test_busy_state_is_observable_without_sleeping(app, busy):
    state = busy()
    assert state.running() is True

    state.process.returncode = 0
    assert state.running() is False


# --- Error paths --- #

def test_pull_data_reports_a_failed_start(tmp_path, analysis_source):
    """A scraper that will not start yields a non-200 and records no pull."""

    # Test double to guarantee failure.
    def boom():
        raise RuntimeError("no browser driver")

    app = create_app(
        {"TESTING": True, "PROPAGATE_EXCEPTIONS": False,
         "PULL_STATUS_PATH": str(tmp_path / "pull_status.json")},
        analysis_source=analysis_source,
        pull_runner=boom,
    )
    response = app.test_client().post("/pull-data")

    assert response.status_code != 200
    assert app.extensions["pull_state"].process is None


def test_failed_pull_writes_no_rows(pull_pipeline):
    """A scrape that fails reaches the loader with nothing, so no rows are written."""

    # Test double to guarantee failure.
    def boom(pages):
        raise RuntimeError("grad cafe unreachable")

    recorder = pull_pipeline(scraper=boom)

    assert pull_data.main() == 1
    assert recorder.loaded == []
    assert recorder.status()["state"] == "failed"


# --- Coverage: the browser paths and the real runner --- #

def test_spawn_pull_launches_the_pull_script(monkeypatch):
    """The production runner starts pull_data.py in its own process."""
    started = {}
    monkeypatch.setattr(subprocess, "Popen",
                        lambda command, cwd: started.setdefault("command", command))

    spawn_pull()

    assert started["command"][1].endswith("pull_data.py")


@pytest.mark.parametrize(
    ("path", "notice"),
    [("/pull-data", "started"), ("/update-analysis", "updated")],
)
def test_browser_posts_redirect_back_to_the_page(client, path, notice):
    """A form post prefers HTML, so it is answered with a redirect, not JSON."""
    response = client.post(path, headers=HTML)

    assert response.status_code == 302
    assert response.headers["Location"] == f"/analysis?notice={notice}"


@pytest.mark.parametrize(
    ("path", "notice"),
    [("/pull-data", "already-running"), ("/update-analysis", "updated-busy")],
)
def test_browser_posts_are_redirected_when_busy(client, busy, path, notice):
    """While a pull runs the browser is redirected with an explanatory notice."""
    busy()
    response = client.post(path, headers=HTML)

    assert response.status_code == 302
    assert response.headers["Location"] == f"/analysis?notice={notice}"
