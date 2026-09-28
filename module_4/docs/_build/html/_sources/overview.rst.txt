Overview and setup
==================

Install
-------

.. code-block:: bash

   python -m pip install -r requirements.txt

Environment
-----------

The application connects to PostgreSQL through ``DATABASE_URL``. With that unset it
falls back to the standard ``PG*`` variables, so no credentials appear in the code.

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Variable
     - Purpose
   * - ``DATABASE_URL``
     - SQLAlchemy URL, e.g. ``postgresql+psycopg://user@localhost:5432/module_4``.
   * - ``PGDATABASE``, ``PGUSER``, ``PGHOST``, ``PGPORT``
     - Used by libpq when ``DATABASE_URL`` is unset.
   * - ``TEST_DATABASE_URL``
     - Optional. Overrides the database the test suite creates and truncates.

.. code-block:: bash

   export PGDATABASE=module_4 PGUSER="$USER" PGHOST=localhost PGPORT=5432
   createdb module_4

Run the application
-------------------

From ``src/``:

.. code-block:: bash

   python load_data.py       # load the cleaned JSON into PostgreSQL
   flask --app app run       # http://127.0.0.1:5000

``python query_data.py`` and ``python orm_queries.py`` print the same eleven answers
from raw SQL and from SQLAlchemy respectively.

The **Pull Data** button needs Firefox installed, because ``scrape.py`` drives it
through Selenium. Nothing else does.

Run the tests
-------------

From ``module_4/``, so pytest finds ``pytest.ini``:

.. code-block:: bash

   python -m pytest

Tests never touch the network or the application database. The ``db`` and
``integration`` tests create and truncate a separate ``module_4_test`` database, and
skip if PostgreSQL is unreachable. See :doc:`testing`.
