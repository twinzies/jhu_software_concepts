"""Reshape scraped Grad Cafe records into the cleaned applicant format."""

import json
from pathlib import Path

SCRAPED_PATH = Path(__file__).parent / "data" / "scraped_data.jsonl"
OUTPUT_PATH = Path(__file__).parent / "applicant_data.json"

def _normalize_status(status_raw):
    """Splits a status such as "Accepted on Jan 09" into the decision and its date."""
    status, _, decision_date = status_raw.partition(" on ")
    return status, decision_date or None

def _combine_program(record):
    """Joins the program and university the way the LLM standardizer expects them."""
    named = [part for part in (record["program"], record["university"]) if part]
    return ", ".join(named) or None

def _clean_record(record):
    """Reshapes one scraped record into the cleaned output format."""
    status, decision_date = _normalize_status(record["status_raw"])

    return {
        "program": _combine_program(record),
        "comments": record["comments"],
        "date_added": record["date_added"],
        "url": record["url"],
        "status": status,
        "decision_date": decision_date,
        "term": record["term"],
        "US/International": record["US/International"],
        "GRE": record["GRE"],
        "GRE V": record["GRE V"],
        "GRE AW": record["GRE AW"],
        "GPA": record["GPA"],
        "Degree": record["degree"],
        # Kept alongside the cleaned fields so every row stays traceable.
        "status_raw": record["status_raw"],
        "details_raw": record["details_raw"],
    }

def _load_scraped(path=SCRAPED_PATH):
    """Reads the scraped records from the JSON Lines file."""
    with open(path, encoding="utf-8") as scraped_file:
        return [json.loads(line) for line in scraped_file if line.strip()]

def clean_data(records)->list[dict]:
    """Converts scraped records into the cleaned, structured format."""
    return [_clean_record(record) for record in records]

def save_data(records, path=OUTPUT_PATH):
    """Saves the cleaned records as a single JSON file."""
    with open(path, "w", encoding="utf-8") as json_file:
        json.dump(records, json_file, ensure_ascii=False, indent=2)

def load_data(path=OUTPUT_PATH)->list[dict]:
    """Loads the cleaned records back from the JSON file."""
    with open(path, encoding="utf-8") as json_file:
        return json.load(json_file)


if __name__ == "__main__":
    cleaned = clean_data(_load_scraped())
    save_data(cleaned)
    print(f"Saved {len(cleaned)} cleaned records to {OUTPUT_PATH.name}")
