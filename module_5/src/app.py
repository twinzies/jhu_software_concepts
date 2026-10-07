"""Flask analysis page with Pull Data and Update Analysis buttons.

Built by the create_app factory so tests can construct an isolated application
that reads fake rows and starts a fake scraper. Run from src/: flask --app app run
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

import models
from models import Applicant, Session
from orm_queries import QUESTIONS, format_value, run_queries

BASE_DIR = Path(__file__).resolve().parent
STATUS_PATH = BASE_DIR / "pull_status.json"
PULL_SCRIPT = BASE_DIR / "pull_data.py"

HEADINGS = {
    "fall_2026_count": "Applicants",
    "percent_international": "Percent International",
    "average_gpa": "Average GPA",
    "average_gre_quantitative": "Average GRE Quantitative",
    "average_gre_verbal": "Average GRE Verbal",
    "average_gre_analytical_writing": "Average GRE Analytical Writing",
    "acceptance_percentage": "Acceptance Percentage",
    "jhu_cs_masters_count": "Entries",
    "original_field_count": "Original Fields",
    "llm_field_count": "LLM Fields",
    "lowest_accepted_gpa": "Lowest Accepted GPA",
    "lowest_american_gpa": "Lowest American GPA",
    "lowest_international_gpa": "Lowest International GPA",
}

NOTICES = {
    "started": ("info", "Data pull started. This page refreshes itself while it runs."),
    "already-running": ("warn", "A data pull is already running, so a second one was not started."),
    "updated": ("ok", "Results refreshed."),
    "updated-busy": (
        "info",
        ("Results refreshed. New data is still being retrieved, "
        "so the newest entries may not appear yet."),
    ),
}


def heading(column):
    """Readable table heading for a result column."""
    return HEADINGS.get(column, column.replace("_", " ").title())


def build_blocks(results):
    """Shape each question's rows so one template block renders all of them."""
    blocks = []
    for number, rows in results.items():
        columns = list(rows[0].keys()) if rows else []
        table = [[format_value(value, column) for column, value in row.items()] for row in rows]
        blocks.append({
            "number": number,
            "question": QUESTIONS.get(number, ""),
            "headings": [heading(column) for column in columns],
            "rows": table,
            "single": len(table) == 1 and len(columns) == 1,
        })
    return blocks


def database_analysis():
    """Read the eleven answers and the row count from PostgreSQL as (blocks, total)."""
    with Session() as session:
        blocks = build_blocks(run_queries(session))
        total = session.scalar(
            select(func.count()).select_from(Applicant)  # pylint: disable=not-callable
        )
    return blocks, total


def spawn_pull():
    """Start pull_data.py in its own process and return the handle."""
    return subprocess.Popen([sys.executable, str(PULL_SCRIPT)], cwd=BASE_DIR)


class PullState:
    """Busy state for the Pull Data button, kept on an instance so tests can inject a fake."""

    def __init__(self, runner=None):
        self.runner = runner or spawn_pull
        self.process = None

    def running(self):
        """Return True while a started pull is still alive."""
        return self.process is not None and self.process.poll() is None

    def start(self):
        """Start a pull and remember the process."""
        self.process = self.runner()
        return self.process

    def died_quietly(self):
        """Return True when the last pull exited non-zero without a status file."""
        return self.process is not None and bool(self.process.poll())


def last_pull(status_path, state):
    """Summarize the most recent pull, or None when nothing is known."""
    status_path = Path(status_path)
    if not status_path.exists():
        # A pull that died before writing is reported.
        if state.died_quietly():
            return {"state": "failed", "when": datetime.now().strftime("%I:%M %p"),
                    "message": "The pull stopped before reporting a result."}
        return None
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    status["when"] = datetime.fromtimestamp(status.get("finished", 0)).strftime("%I:%M %p")
    return status


def wants_json():
    """Answer button posts with JSON unless the caller ranks HTML higher, as browsers do."""
    accept = request.accept_mimetypes
    return accept["application/json"] >= accept["text/html"]


def create_app(config=None, *, analysis_source=None, pull_runner=None):
    """Build the app, letting tests override config and inject fake data and scraper callables."""
    flask_app = Flask(__name__)
    flask_app.config.update(
        DATABASE_URL=os.environ.get("DATABASE_URL", ""),
        PULL_STATUS_PATH=str(STATUS_PATH),
    )
    flask_app.config.update(config or {})

    if flask_app.config["DATABASE_URL"]:
        models.configure(flask_app.config["DATABASE_URL"])

    flask_app.extensions["analysis_source"] = analysis_source or database_analysis
    flask_app.extensions["pull_state"] = PullState(pull_runner)

    @flask_app.get("/")
    @flask_app.get("/analysis")
    def analysis():
        """Render the analysis page; both paths serve it so older links keep working."""
        state = current_app.extensions["pull_state"]
        blocks, total, error = [], None, None
        try:
            blocks, total = current_app.extensions["analysis_source"]()
        except SQLAlchemyError as database_error:
            error = (f"Could not read the database: {database_error}. "
                     "Check that PostgreSQL is running and DATABASE_URL or the "
                     "PG* variables are set.")

        return render_template(
            "index.html",
            blocks=blocks,
            total=total,
            error=error,
            notice=NOTICES.get(request.args.get("notice", "")),
            pulling=state.running(),
            pull=last_pull(current_app.config["PULL_STATUS_PATH"], state),
            generated=datetime.now().strftime("%b %d, %Y at %I:%M:%S %p"),  # noqa: DTZ005
        )

    @flask_app.post("/pull-data")
    def pull_data():
        """Start a scrape unless one is already in progress."""
        state = current_app.extensions["pull_state"]
        if state.running():
            if wants_json():
                return jsonify(busy=True), 409
            return redirect(url_for("analysis", notice="already-running"))

        Path(current_app.config["PULL_STATUS_PATH"]).unlink(missing_ok=True)
        state.start()
        if wants_json():
            return jsonify(ok=True), 202
        return redirect(url_for("analysis", notice="started"))

    @flask_app.post("/update-analysis")
    def update_analysis():
        """Re-run the queries, unless a pull is still writing rows."""
        state = current_app.extensions["pull_state"]
        if state.running():
            if wants_json():
                return jsonify(busy=True), 409
            return redirect(url_for("analysis", notice="updated-busy"))

        if wants_json():
            return jsonify(ok=True), 200
        return redirect(url_for("analysis", notice="updated"))

    return flask_app


app = create_app()


if __name__ == "__main__":
    app.run()
