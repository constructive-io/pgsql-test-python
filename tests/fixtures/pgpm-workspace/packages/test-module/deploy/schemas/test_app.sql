-- Deploy test-module:schemas/test_app to pg

BEGIN;

CREATE SCHEMA test_app;

COMMIT;
