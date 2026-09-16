"""
Row-level security tests.

These prove that `db` is a genuinely separate, non-superuser connection
(app_user) that is subject to role grants and RLS policies, while `pg`
is the superuser that bypasses them. If `db` were ever aliased to `pg`
again, every test in this module would fail.
"""

import psycopg2
import pytest

from pgsql_test import get_connections

SCHEMA = """
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL
);

INSERT INTO documents (owner_id, title) VALUES
    ('alice', 'alice-doc-1'),
    ('alice', 'alice-doc-2'),
    ('bob', 'bob-doc-1');

ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT ON documents TO authenticated;
GRANT USAGE ON SEQUENCE documents_id_seq TO authenticated;

CREATE POLICY documents_owner_select ON documents
    FOR SELECT TO authenticated
    USING (owner_id = current_setting('jwt.claims.user_id', true));

CREATE POLICY documents_owner_insert ON documents
    FOR INSERT TO authenticated
    WITH CHECK (owner_id = current_setting('jwt.claims.user_id', true));
"""


@pytest.fixture(scope="module")
def conn():
    connection = get_connections()
    connection.pg.query(SCHEMA)
    connection.pg.commit()
    yield connection
    connection.teardown()


@pytest.fixture
def db(conn):
    conn.db.before_each()
    yield conn.db
    conn.db.clear_context()
    conn.db.after_each()


@pytest.fixture
def pg(conn):
    conn.pg.before_each()
    yield conn.pg
    conn.pg.after_each()


def test_db_and_pg_are_different_connections(conn):
    assert conn.db is not conn.pg
    assert conn.pg.config["user"] != conn.db.config["user"]
    assert conn.db.config["user"] == "app_user"

    pg_who = conn.pg.one("SELECT current_user, session_user, usesuper FROM pg_user "
                         "WHERE usename = session_user")
    db_who = conn.db.one("SELECT current_user, session_user, usesuper FROM pg_user "
                         "WHERE usename = session_user")
    assert pg_who["usesuper"] is True
    assert db_who["usesuper"] is False
    assert db_who["session_user"] == "app_user"
    # default context role is applied on every query
    assert db_who["current_user"] == "anonymous"


def test_superuser_pg_bypasses_rls(pg):
    rows = pg.many("SELECT title FROM documents ORDER BY id")
    assert len(rows) == 3


def test_anonymous_has_no_table_access(db):
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        db.query("SELECT * FROM documents")


def test_authenticated_sees_only_own_rows(db):
    db.set_context({"role": "authenticated", "jwt.claims.user_id": "alice"})
    rows = db.many("SELECT title FROM documents ORDER BY id")
    assert [r["title"] for r in rows] == ["alice-doc-1", "alice-doc-2"]

    db.set_context({"jwt.claims.user_id": "bob"})
    rows = db.many("SELECT title FROM documents ORDER BY id")
    assert [r["title"] for r in rows] == ["bob-doc-1"]


def test_authenticated_without_claims_sees_nothing(db):
    db.set_context({"role": "authenticated"})
    result = db.query("SELECT title FROM documents")
    assert result.rows == []


def test_insert_policy_enforced(db):
    db.set_context({"role": "authenticated", "jwt.claims.user_id": "alice"})

    db.execute("INSERT INTO documents (owner_id, title) VALUES ('alice', 'alice-doc-3')")
    rows = db.many("SELECT title FROM documents ORDER BY id")
    assert len(rows) == 3

    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        db.execute("INSERT INTO documents (owner_id, title) VALUES ('bob', 'forged')")


def test_insert_rolled_back_between_tests(db):
    db.set_context({"role": "authenticated", "jwt.claims.user_id": "alice"})
    rows = db.many("SELECT title FROM documents ORDER BY id")
    assert [r["title"] for r in rows] == ["alice-doc-1", "alice-doc-2"]


def test_clear_context_restores_default_role(db):
    db.set_context({"role": "authenticated", "jwt.claims.user_id": "alice"})
    assert db.one("SELECT current_user AS u")["u"] == "authenticated"

    db.clear_context()
    assert db.one("SELECT current_user AS u")["u"] == "anonymous"
    assert db.one("SELECT current_setting('jwt.claims.user_id', true) AS v")["v"] in (None, "")


def test_administrator_role_membership_is_granted(conn, db):
    # Schema change must be committed before db (which holds an open tx) reads it.
    conn.pg.query("GRANT SELECT ON documents TO administrator")
    conn.pg.query(
        "CREATE POLICY documents_admin_select ON documents FOR SELECT TO administrator USING (true)"
    )
    conn.pg.commit()

    db.set_context({"role": "administrator"})
    rows = db.many("SELECT title FROM documents")
    assert len(rows) == 3
