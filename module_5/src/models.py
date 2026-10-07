"""SQLAlchemy model and session factory for the applicants table."""

import os
from datetime import date

from sqlalchemy import Date, Float, Identity, Integer, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


# Declarative models hold columns, not methods.
class Base(DeclarativeBase):  # pylint: disable=too-few-public-methods
    """Base class for SQLAlchemy models."""


class Applicant(Base):  # pylint: disable=too-few-public-methods
    """One Grad Cafe submission in the existing applicants table."""

    __tablename__ = "applicants"

    p_id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)

    # Optional fields allow NULL, matching the table created by load_data.py.
    program: Mapped[str | None] = mapped_column(Text)
    comments: Mapped[str | None] = mapped_column(Text)
    date_added: Mapped[date | None] = mapped_column(Date)
    url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    term: Mapped[str | None] = mapped_column(Text)
    us_or_international: Mapped[str | None] = mapped_column(Text)
    gpa: Mapped[float | None] = mapped_column(Float(53))
    gre: Mapped[float | None] = mapped_column(Float(53))
    gre_v: Mapped[float | None] = mapped_column(Float(53))
    gre_aw: Mapped[float | None] = mapped_column(Float(53))
    degree: Mapped[str | None] = mapped_column(Text)
    llm_generated_program: Mapped[str | None] = mapped_column(Text)
    llm_generated_university: Mapped[str | None] = mapped_column(Text)


# With no DATABASE_URL the psycopg driver reads the PG* environment variables.
DEFAULT_DATABASE_URL = "postgresql+psycopg://"


def database_url():
    """Return the connection URL, preferring DATABASE_URL over the PG* variables."""
    return os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL


def make_engine(url=None):
    """Build an engine for the URL, timing out only on PostgreSQL connections."""
    url = url or database_url()
    connect_args = {"connect_timeout": 10} if url.startswith("postgresql") else {}
    return create_engine(url, connect_args=connect_args)


# Session is a factory class, so it keeps SQLAlchemy's CapWords convention.
Session = sessionmaker(bind=make_engine())  # pylint: disable=invalid-name


def configure(url):
    """Point the shared Session at another database, so tests can override it."""
    engine = make_engine(url)
    Session.configure(bind=engine)
    return engine
