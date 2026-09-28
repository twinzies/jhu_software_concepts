"""Task 1: Flask app factory, routes, and rendering of the analysis page."""

import pytest
from app import create_app
from flask import Flask
from flask.testing import FlaskClient

pytestmark = pytest.mark.web

ROUTES = [
    ("/", "GET"),
    ("/analysis", "GET"),
    ("/pull-data", "POST"),
    ("/update-analysis", "POST"),
]


def rules(app):
    """Map each registered path to the methods it accepts."""
    return {rule.rule: rule.methods for rule in app.url_map.iter_rules()}


# --- 1a. App factory and configuration  --- #

def test_factory_returns_a_flask_app(app):
    assert isinstance(app, Flask)


def test_factory_builds_a_testable_app(app):
    assert app.config["TESTING"] is True
    assert isinstance(app.test_client(), FlaskClient)


def test_factory_injects_the_analysis_source(app, analysis_source):
    assert app.extensions["analysis_source"] is analysis_source


def test_factory_injects_the_pull_runner(app):
    assert app.extensions["pull_state"].process is None
    assert app.extensions["pull_state"].runner is not None


def test_config_can_be_overridden_by_tests(tmp_path):
    url = "postgresql+psycopg://localhost/module_4_test"
    status = tmp_path / "status.json"
    app = create_app({"TESTING": True, "DATABASE_URL": url, "PULL_STATUS_PATH": str(status)})

    assert app.config["DATABASE_URL"] == url
    assert app.config["PULL_STATUS_PATH"] == str(status)


def test_factory_returns_independent_apps(analysis_source, pull_runner):
    first = create_app({"TESTING": True}, analysis_source=analysis_source,
                       pull_runner=pull_runner)
    second = create_app({"TESTING": True}, analysis_source=analysis_source,
                        pull_runner=pull_runner)

    assert first is not second
    assert first.extensions["pull_state"] is not second.extensions["pull_state"]


# --- 1a. Required routes  --- #

@pytest.mark.parametrize(("path", "method"), ROUTES)
def test_required_route_is_registered(app, path, method):
    registered = rules(app)
    assert path in registered, f"{path} is not registered"
    assert method in registered[path]


@pytest.mark.parametrize(("path", "method"), ROUTES)
def test_every_route_responds(client, path, method):
    """No route is missing or mis-wired: check for 40x error codes"""
    response = client.open(path, method=method)
    assert response.status_code not in (404, 405)


# --- 1b. GET /analysis --- #

def test_analysis_page_returns_200(client):
    """1b-i."""
    assert client.get("/analysis").status_code == 200


def test_index_serves_the_same_analysis_page(app, client):
    """Both paths resolve to one endpoint; the HTML differs only by its timestamp."""
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()
                 if rule.rule in ("/", "/analysis")}

    assert endpoints == {"analysis"}
    assert client.get("/").status_code == 200


@pytest.mark.parametrize(
    ("testid", "label"),
    [("pull-data-btn", "Pull Data"), ("update-analysis-btn", "Update Analysis")],
)
def test_page_contains_both_buttons(page, testid, label):
    button = page.select_one(f'[data-testid="{testid}"]')
    assert button is not None, f"no element with data-testid={testid!r}"
    assert button.get_text(strip=True) == label


@pytest.mark.parametrize(
    ("testid", "endpoint"),
    [("pull-data-btn", "/pull-data"), ("update-analysis-btn", "/update-analysis")],
)
def test_each_button_posts_to_its_endpoint(page, testid, endpoint):
    """The buttons are wired to the routes, not just present as decoration."""
    form = page.select_one(f'[data-testid="{testid}"]').find_parent("form")
    assert form is not None
    assert form["method"].lower() == "post"
    assert form["action"] == endpoint


def test_page_text_includes_analysis(page):
    assert "Analysis" in page.title.get_text()
    assert "Analysis" in page.get_text()


def test_page_includes_at_least_one_answer_label(page):
    """1b-iii, second half."""
    labels = [element.get_text(strip=True) for element in page.select(".answer-label")]
    assert labels, "the page renders no Answer: label"
    assert all(label == "Answer:" for label in labels)


def test_every_rendered_question_is_labelled(page):
    """The Answer: label is consistent, not present on one lucky card."""
    cards = page.select("section.card")
    assert cards, "the page renders no analysis cards"
    for card in cards:
        assert "Answer:" in card.get_text(), f"card {card.h2.get_text()} has no Answer: label"
