"""Task 3: Testing answer labels and two-decimal formatting of rendered analysis."""

import re
from decimal import Decimal
import pytest
from orm_queries import format_value
pytestmark = pytest.mark.analysis

def test_rendered_answers_are_labelled(page):
    cards = page.select("section.card")
    assert cards, "the page renders no analysis cards"
    for card in cards:
        assert "Answer:" in card.get_text(), f"{card.h2.get_text()} has no Answer: label"


def test_percentages_rendered_with_two_decimals(page):
    percentages = re.compile(r"\d+(?:\.\d+)?%").findall(page.get_text())
    assert percentages, "the page renders no percentage to check"
    for percentage in percentages:
        assert re.compile(r"^\d+\.\d{2}%$").match(percentage), f"{percentage} is not a two-decimal percentage"


@pytest.mark.parametrize(
    ("value", "expected"),
    [(3.5, "3.50"), (39.2837, "39.28"), (Decimal("39.285"), "39.28"), (None, "N/A")],
)
def test_value_rounds_to_two_decimals(value, expected):
    """The rounding the page depends on lives in format_value."""
    assert format_value(value, "average_gpa") == expected