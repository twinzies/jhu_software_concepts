"""Sphinx configuration for the Grad Cafe analytics application."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

project = "Grad Cafe Analytics"
author = "twinzies"
release = "1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

html_theme = "sphinx_rtd_theme"
autodoc_member_order = "bysource"

# For SQLAlchemy's inherited attributes
autodoc_default_options = {"exclude-members": "metadata, registry"}
