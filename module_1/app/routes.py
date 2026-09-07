"""Page routes for the personal website.

Every page is served by the main blueprint. The blueprint keeps the
routes separate from the application setup in app/__init__.py.
"""

from flask import Blueprint, render_template

main = Blueprint("main", __name__)


@main.route("/")
def home():
    """Home page: name, position, biography and photo."""
    return render_template("home.html")


@main.route("/projects")
def projects():
    """Projects and publications, starting with the Module 1 project."""
    return render_template("projects.html")


@main.route("/contact")
def contact():
    """Contact details: email address and LinkedIn."""
    return render_template("contact.html")
