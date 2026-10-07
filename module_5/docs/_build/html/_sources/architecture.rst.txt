Architecture
============

The application is organized into three layers: Web, ETL, and Database.
The Web layer presents analysis and starts data pulls. The ETL layer scrapes, cleans, and loads applicant records. The Database layer stores those records and supports analysis queries.

Web
---

``app.py`` exposes a :func:`app.create_app` factory. It serves the analysis page at
``/`` and ``/analysis``, and accepts ``POST /pull-data`` and ``POST /update-analysis``.

Two dependencies are injected so tests can replace them: ``analysis_source`` (returns the rendered blocks and the row total) and ``pull_runner`` (starts the scraper).

:class:`app.PullState` holds the running pull on the application instance rather than in a module global, which makes the busy state observable instead of timing-dependent.

Button responses are content negotiated: browsers get a redirect back to the page,
JSON clients get ``{"ok": true}`` (200/202) or ``{"busy": true}`` (409).

ETL
---

``pull_data.main()`` runs the pipeline end to end:

.. code-block:: text

   scrape.scrape_newest -> pull_data.save_raw -> clean.clean_data
       -> load_data.to_row -> load_data.load_records

``scrape.py`` drives headless Firefox and parses results with BeautifulSoup, retrying and restarting the driver on timeouts. ``clean.py`` reshapes raw records into the Module 2 format. ``pull_data.py`` writes ``pull_status.json`` so the page can report how the last pull finished.

Database
--------

``models.py`` defines the ``applicants`` table and a ``Session`` factory, and exposes :func:`models.configure` so tests can rebind it to another database.

``load_data.load_records`` is the only writer. It locks the table, reads the existing URLs, and inserts only unseen rows inside one transaction, so repeated pulls cannot create duplicates. The URL is the uniqueness key; rows without one are compared whole.

``query_data.py`` answers the eleven questions in raw SQL, ``orm_queries.py`` in SQLAlchemy. The page uses the ORM version through ``run_queries``.
