"""Application factory for the Module 1 Flask project - personal website."""

from flask import Flask

from app.routes import main


def create_app():
    """Build and configure the Flask application."""
    app = Flask(__name__)

    # All pages live in a single blueprint - see app/routes.py.
    app.register_blueprint(main)

    return app
