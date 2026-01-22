-- Revert test-module:schemas/test_app from pg

BEGIN;

DROP SCHEMA IF EXISTS test_app CASCADE;

COMMIT;
