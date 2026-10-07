-- Create the app's least-privilege login. Run as the database owner, after schema.sql:
--   psql -d module_4 -v app_password="$DB_PASSWORD" -f db/least_privilege.sql
--
-- The app only reads applicants (analysis page) and appends new rows (Pull Data),
-- so it gets SELECT and INSERT on that one table: no UPDATE, DELETE, TRUNCATE,
-- DROP or ALTER, no ownership, and no CREATE anywhere.

CREATE ROLE gradcafe_app LOGIN PASSWORD :'app_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

-- PostgreSQL 15+ already denies CREATE on public to ordinary users; make it explicit.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

SELECT format('GRANT CONNECT ON DATABASE %I TO gradcafe_app', current_database()) \gexec
GRANT USAGE ON SCHEMA public TO gradcafe_app;
GRANT SELECT, INSERT ON TABLE applicants TO gradcafe_app;
