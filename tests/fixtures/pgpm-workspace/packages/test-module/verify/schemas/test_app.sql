-- Verify test-module:schemas/test_app on pg

BEGIN;

SELECT pg_catalog.has_schema_privilege('test_app', 'usage');

ROLLBACK;
