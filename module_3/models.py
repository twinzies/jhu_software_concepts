"""Part 5A"""

from datetime import date

from sqlalchemy import Date, Float, Identity, Integer, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


class Applicant(Base):
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


# The psycopg driver reads the PG* environment variables.
engine = create_engine("postgresql+psycopg://", connect_args={"connect_timeout": 10})

Session = sessionmaker(bind=engine)

