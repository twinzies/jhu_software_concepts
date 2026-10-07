# Module 4

The project in src/ is the flask app built in module_3 which loads the cleaned Module 2 applicant data into PostgreSQL, answers the eleven analysis
questions in both raw SQL and SQLAlchemy, and serves the results as a Flask page with Pull Data and Update Analysis buttons. This module_4 expands on that work with a test suite using pytest and documentation with sphinx.

**Github SSH URL for this repo:** `git@github.com:twinzies/jhu_software_concepts.git`

### ()
Pylint was run on this repository with the following command:

```bash
pylint src
```

## Setup

Use the same Python environment for installing and running. The local setup uses Conda base,
`/opt/miniconda3/bin/python`, Python 3.12.

```bash
python -m pip install -r requirements.txt
```

or alternatively, in a virtual environment: 

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```
Export the environment variables with the following commands:

```bash
export PGDATABASE=module_4
export PGUSER="$USER"
export PGHOST=localhost
export PGPORT=5432
```

Create the database once, if it does not already exist:

```bash
createdb module_4
```

The login role must already exist. Connection settings come from PostgreSQL's
`PG*` environment variables, so no credentials appear in the code and nothing prompts for a password. Export the variables before starting Flask, because the Pull Data subprocess inherits them from the server.

pull_data.py needs Firefox installed. The rest of the page works without Firefox; only the Pull Data button needs it so that Selenium can bypass the Cloudflare restriction on grad cafe when scraping with scrape.py.

## Running

```bash
python src/load_data.py       # load the JSON into PostgreSQL
python src/query_data.py      # raw SQL, Q1-Q11 - see query_results.pdf for descriptions
python src/orm_queries.py     # SQLAlchemy answers, same numbering.
flask --app app run       # app at http://127.0.0.1:5000
```

Run `query_data.py` and `orm_queries.py` from this folder. Both print one line per question,
and the two should match exactly:

```bash
diff <(python query_data.py) <(python orm_queries.py)
```

## SQL Injection Defenses

All SQL is built with psycopg's `sql.SQL` composition: table and column names are quoted with `sql.Identifier`, and every value is a bound placeholder passed separately to `cursor.execute(statement, params)`. No query is built with f-strings, `+`, or `.format()` on raw SQL text.
Every query ends in `LIMIT %(limit)s`. `sql_safety.clamp_limit` clamps the limit to 1–100 and replaces non-numeric input such as `/analysis?limit=1;DROP TABLE applicants` with the default (`tests/test_sql_injection.py`).

## Testing

Run from this folder so pytest finds `pytest.ini`. No database or network is needed.

```bash
python -m pytest                                                    # whole suite, with coverage
python -m pytest -m "web or buttons or analysis or db or integration"   # same, by marker
```

## Documentation

Published Sphinx docs: **https://jhu-software-concepts2.readthedocs.io/en/latest/api.html** — overview and
setup, architecture, API reference, and the testing guide.

Build them locally into `docs/_build/html`:

```bash
python -m sphinx -b html docs docs/_build/html
```
