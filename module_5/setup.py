"""Package the Grad Cafe analysis app."""

from pathlib import Path

from setuptools import setup

SRC = Path(__file__).resolve().parent / "src"

setup(
    name="gradcafe-analysis",
    version="5.0.0",
    description="Flask + PostgreSQL analysis of Grad Cafe admissions data, hardened against SQLi.",
    python_requires=">=3.10",
    package_dir={"": "src"},
    py_modules=sorted(path.stem for path in SRC.glob("*.py")),
    install_requires=[
        "psycopg[binary]>=3.2,<4",
        "SQLAlchemy>=2.0,<3",
        "Flask>=3.0,<4",
        "beautifulsoup4>=4.12",
        "selenium>=4.20",
        "urllib3>=2.0",
    ],
    extras_require={
        "dev": ["pytest>=8.0", "pytest-cov>=5.0", "pylint>=3.0", "pydeps>=3.0"],
    },
)
