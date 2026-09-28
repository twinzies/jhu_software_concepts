Testing guide
=============

118 tests with pytest, all offline, run in under a second, 100% coverage.

Markers
-------

Every test carries exactly one marker, declared in ``pytest.ini``. No test is
unmarked, so the expression below runs the whole suite.

.. list-table::
   :header-rows: 1
   :widths: 20 45 35

   * - Marker
     - Covers
     - File
   * - ``web``
     - app factory, routes, page rendering
     - ``test_flask_page.py``
   * - ``buttons``
     - button endpoints and busy-state gating
     - ``test_buttons.py``
   * - ``analysis``
     - Answer labels and two-decimal formatting
     - ``test_analysis_format.py``
   * - ``db``
     - inserts, uniqueness, queries, ETL modules
     - ``test_db_insert.py``, ``test_etl.py``, ``test_scrape.py``
   * - ``integration``
     - pull to update to render
     - ``test_integration_end_to_end.py``

.. code-block:: bash

   python -m pytest -m "web or buttons or analysis or db or integration"   # everything
   python -m pytest -m buttons                                             # one group

``--strict-markers`` is on, so a mistyped marker fails rather than silently
selecting nothing.

Selectors
---------

UI assertions use stable attributes, never CSS classes or button text position.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Selector
     - Element
   * - ``[data-testid="pull-data-btn"]``
     - Pull Data button
   * - ``[data-testid="update-analysis-btn"]``
     - Update Analysis button
   * - ``[data-testid="answer"]`` / ``.answer-label``
     - the ``Answer:`` label on each card
   * - ``section.card``
     - one analysis question

Fixtures and test doubles
-------------------------

Shared fixtures live in ``tests/conftest.py``.

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Fixture
     - Provides
   * - ``app`` / ``client`` / ``page``
     - a testable app, Flask's test client, and the parsed ``/analysis`` HTML
   * - ``analysis_source``
     - fake query results, counting its calls so a refresh is observable
   * - ``pull_runner``, ``busy``
     - a finished pull, and a way to force the in-progress state
   * - ``scraped_records``
     - three fake scraper records in the shape ``clean`` expects
   * - ``pull_pipeline``
     - wires ``pull_data.main()`` to fake scrape and database stages
   * - ``db_url``, ``db_connection``, ``db_session``
     - an empty ``applicants`` table on a separate ``module_4_test`` database
   * - ``loading_app``, ``end_to_end_app``
     - apps whose Pull Data button writes to that test database

Doubles: ``FakeProcess`` stands in for ``subprocess.Popen``, with ``poll()``
returning ``None`` while a pull looks busy, so busy-state tests set a value instead
of sleeping. ``FakeDriver`` replaces the Selenium driver and can be told to fail on
``quit()``. ``FakeConnection`` stands in for ``psycopg.connect``.

Coverage
--------

``pytest.ini`` enforces ``--cov-fail-under=100`` over ``src/``. ``.coveragerc``
excludes only ``if __name__ == "__main__":`` blocks. The committed summary is
``coverage_summary.txt``:

.. code-block:: bash

   python -m pytest > coverage_summary.txt 2>&1
