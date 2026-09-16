-- Deploy test-module:schemas/test_app to pg

BEGIN;

CREATE SCHEMA test_app;

GRANT USAGE ON SCHEMA test_app TO anonymous, authenticated, administrator;

COMMIT;
