# Module 4

The project in src/ is the flask app built in module_3 which loads the cleaned Module 2 applicant data into PostgreSQL, answers the eleven analysis
questions in both raw SQL and SQLAlchemy, and serves the results as a Flask page with Pull Data and Update Analysis buttons. This module_4 expands on that work with a test suite using pytest and documentation with sphinx.

**Github SSH URL for this repo:** `git@github.com:twinzies/jhu_software_concepts.git`

### New - Pylint
Pylint was run on this repository with the following command:

```bash
pylint src
```

## Fresh Install

Requires Python 3.10+, PostgreSQL, and Graphviz (for `pydeps`; on macOS: `brew install graphviz`). Run from `module_5/`.

**pip + venv**

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

**uv**

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip install -e .
```

`requirements.txt` holds the runtime packages plus the tooling (pytest, pylint, pydeps). `pip install -e .` installs the project itself from `setup.py` as an editable package, so `app`, `query_data`, `db` and the other modules in `src/` import the same way from any folder, in tests, and in CI.

### Database and environment variables

The app reads its connection only from `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` and `DB_PASSWORD` (`src/db.py`); no credentials are in the code. Copy `.env.example` to `.env` (git-ignored), set a password, and load it into your shell before running anything, so the Pull Data subprocess inherits it:

```bash
cp .env.example .env
set -a; source .env; set +a
```

As the database owner, create the database and table, then the app's least-privilege login, `gradcafe_app`. It is not a superuser and has only `SELECT` and `INSERT` on `applicants`: no `UPDATE`, `DELETE`, `DROP`, `ALTER` or `CREATE`.

```bash
createdb module_4
psql -d module_4 -f db/schema.sql
psql -d module_4 -v app_password="$DB_PASSWORD" -f db/least_privilege.sql
```

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
