"""Parts 8-10: analysis page with Pull Data and Update Analysis buttons.

Run from module_3: flask --app app run
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for
from models import Applicant, Session
from orm_queries import QUESTIONS, format_value, run_queries
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

BASE_DIR = Path(__file__).resolve().parent
STATUS_PATH = BASE_DIR / "pull_status.json"

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

app = Flask(__name__)
process = None


def running():
    return process is not None and process.poll() is None


def heading(column):
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


def last_pull():
    if not STATUS_PATH.exists():
        # A pull that died before writing is reported.
        if process is not None and process.poll():
            return {"state": "failed", "when": datetime.now().strftime("%I:%M %p"),
                    "message": "The pull stopped before reporting a result."}
        return None
    try:
        status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    status["when"] = datetime.fromtimestamp(status.get("finished", 0)).strftime("%I:%M %p")
    return status


@app.get("/")
def index():
    blocks, total, error = [], None, None
    try:
        with Session() as session:
            blocks = build_blocks(run_queries(session))
            total = session.scalar(select(func.count()).select_from(Applicant))
    except SQLAlchemyError as database_error:
        error = (f"Could not read the database: {database_error}. "
                 "Check that PostgreSQL is running and the PG* variables are set.")

    return render_template(
        "index.html",
        blocks=blocks,
        total=total,
        error=error,
        notice=NOTICES.get(request.args.get("notice", "")),
        pulling=running(),
        pull=last_pull(),
        generated=datetime.now().strftime("%b %d, %Y at %I:%M:%S %p"),
    )


@app.post("/pull-data")
def pull_data():
    global process
    if running():
        return redirect(url_for("index", notice="already-running"))

    STATUS_PATH.unlink(missing_ok=True)
    process = subprocess.Popen([sys.executable, str(BASE_DIR / "pull_data.py")], cwd=BASE_DIR)
    return redirect(url_for("index", notice="started"))


@app.post("/update-analysis")
def update_analysis():
    # Re-runs the queries.
    return redirect(url_for("index", notice="updated-busy" if running() else "updated"))


if __name__ == "__main__":
    app.run()
