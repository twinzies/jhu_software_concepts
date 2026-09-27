# Module 3

Loads the cleaned Module 2 applicant data into PostgreSQL, answers the eleven analysis
questions in both raw SQL and SQLAlchemy, and serves the results as a Flask page with
Pull Data and Update Analysis buttons.

## Setup

Use the same Python environment for installing and running. The local setup uses Conda base,
`/opt/miniconda3/bin/python`, Python 3.12.

```bash
python -m pip install -r requirements.txt

export PGDATABASE=module_3
export PGUSER=postgres
export PGHOST=localhost
export PGPORT=5432
```

Create the database once, if it does not already exist:

```bash
createdb module_3
```

The login role must already exist. Connection settings come from PostgreSQL's
`PG*` environment variables, so no credentials appear in the code and nothing prompts for a password. Export the variables before starting Flask, because the Pull Data subprocess inherits them from the server.

pull_data.py needs Firefox installed. The rest of the page works without Firefox; only the Pull Data button needs it so that Selenium can bypass the Cloudflare restriction on grad cafe when scraping with scrape.py.

## Running

```bash
python load_data.py       # load the JSON into PostgreSQL
python query_data.py      # raw SQL, Q1-Q11 - see query_results.pdf for descriptions
python orm_queries.py     # SQLAlchemy answers, same numbering.
flask --app app run       # app at http://127.0.0.1:5000
```

Run `query_data.py` and `orm_queries.py` from this folder. Both print one line per question,
and the two should match exactly:

```bash
diff <(python query_data.py) <(python orm_queries.py)
```

## SQL versus SQLAlchemy (Part 7)

Question 1, "How many entries are from applicants who applied for Fall 2026?"

Raw SQL, from `query_data.py`:

```sql
SELECT COUNT(*) AS fall_2026_count
FROM applicants
WHERE LOWER(term) = 'fall 2026';
```

SQLAlchemy, from `orm_queries.py`:

```python
select(func.count().label("fall_2026_count"))
    .select_from(Applicant)
    .where(func.lower(Applicant.term) == "fall 2026")
```

**Advantage of ORM**: The ORM builds a query out of Python objects, so shared pieces can be named and reused:
`accepted_phd` is written once and used by Questions 8, 9, 10 and 11, while the raw SQL
repeats those same three filters in each of those queries making it more verbose. SQLAlchemy also binds values for
us and checks column names against the model, so a typo like `Applicant.trm` fails straight
away instead of becoming a database error. 

**Advantage of SQL**: Raw SQL is easier to debug, because
the text in the file is exactly what PostgreSQL runs and can be pasted into `psql` unchanged, whereas the ORM version has to be compiled before you can see the SQL it produced. Neither approach is better everywhere: the ORM paid off for the
filters repeated across several questions, and plain SQL was simpler for the one-off averages.

## Known limitations

- Records added by Pull Data have no `llm_generated_program` or `llm_generated_university`
  value, because the Module 2 standardizer is not part of the button. Questions 9, 10 and 11 read those columns, so they do not count newly pulled entries until the standardizer is run and the data is reloaded.
- Pull Data reads the three newest pages. Entries older than that are not picked up.
