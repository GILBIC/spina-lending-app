"""Book isolation contracts; run only on the task-owned synthetic database."""

import os
import re
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

DATABASE_URL = os.getenv("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="Disposable PostgreSQL URL is not configured"
)
MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "0140_add_accounting_book_identity.sql"
)


@pytest.fixture
def book_db(request):
    assert os.getenv("SPINA_ALLOW_DISPOSABLE_DATABASE") == "1"
    assert DATABASE_URL is not None
    from psycopg.conninfo import conninfo_to_dict

    parameters = conninfo_to_dict(DATABASE_URL)
    assert parameters.get("host") in {"127.0.0.1", "localhost", "::1"}
    assert parameters.get("hostaddr", parameters["host"]) in {
        "127.0.0.1",
        "localhost",
        "::1",
    }
    assert not {"service", "servicefile", "options", "passfile"}.intersection(
        parameters
    )
    assert re.fullmatch(
        r"spina_treasury_validation_[a-f0-9]{24}", parameters.get("dbname", "")
    )
    with psycopg.connect(DATABASE_URL) as connection:
        try:
            if getattr(request, "param", None) == "repeatable read":
                connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            if MIGRATION.exists():
                migration = MIGRATION.read_text(encoding="utf-8").strip()
                connection.execute(migration[len("BEGIN;") : -len("COMMIT;")])
            actor = connection.execute(
                "INSERT INTO core.users(username,full_name,status) VALUES(%s,'Synthetic Book Manager','active') RETURNING id",
                (f"book-manager-{uuid4().hex}",),
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO core.user_roles(user_id,role_id) SELECT %s,id FROM core.roles WHERE code='management'",
                (actor,),
            )
            yield connection, actor
        finally:
            connection.rollback()


def configure(connection, actor, kind="synthetic", **changes):
    values = {
        "kind": kind,
        "label": "Synthetic book",
        "reference": "test-evidence:book-identity",
        "digest": "a" * 64,
    }
    values.update(changes)
    return connection.execute(
        "SELECT accounting.configure_book_identity(%s,%s,%s,%s,%s)",
        (values["kind"], values["label"], values["reference"], values["digest"], actor),
    ).fetchone()[0]


def context(connection, actor, kind):
    context_id = uuid4()
    connection.execute(
        "INSERT INTO treasury.contexts(id,kind,created_by) VALUES(%s,%s,%s)",
        (context_id, kind, actor),
    )
    return context_id


def account(connection, actor, context_id, ownership, *, active=True):
    account_id = uuid4()
    connection.execute(
        """INSERT INTO treasury.accounts(id,ledger_context_id,kind,alias,ownership,custodian_user_id,active)
           VALUES(%s,%s,'physical_cash','Synthetic test wallet',%s,%s,%s)""",
        (account_id, context_id, ownership, actor, active),
    )
    return account_id


def test_unconfigured_identity_is_explicit_and_never_seeded(book_db):
    connection, actor = book_db
    assert (
        connection.execute("SELECT to_regclass('accounting.book_identity')").fetchone()[
            0
        ]
        is not None
    ), "Book identity migration is missing"
    assert (
        connection.execute("SELECT count(*) FROM accounting.book_identity").fetchone()[
            0
        ]
        == 0
    )
    context_id = context(connection, actor, "synthetic")
    with pytest.raises(psycopg.Error, match="unconfigured"), connection.transaction():
        connection.execute(
            "SELECT accounting.require_book_treasury_context(%s)", (context_id,)
        )


def test_exact_retry_retains_id_actor_timestamp_and_evidence(book_db):
    connection, actor = book_db
    book_id = configure(connection, actor)
    before = connection.execute(
        "SELECT to_jsonb(b) FROM accounting.book_identity b"
    ).fetchone()[0]
    assert configure(connection, actor) == book_id
    assert (
        connection.execute(
            "SELECT to_jsonb(b) FROM accounting.book_identity b"
        ).fetchone()[0]
        == before
    )


def test_another_manager_is_not_the_original_setup_retry(book_db):
    connection, actor = book_db
    configure(connection, actor)
    other = connection.execute(
        "INSERT INTO core.users(username,full_name,status) VALUES(%s,'Other Manager','active') RETURNING id",
        (uuid4().hex,),
    ).fetchone()[0]
    connection.execute(
        "INSERT INTO core.user_roles(user_id,role_id) SELECT %s,id FROM core.roles WHERE code='management'",
        (other,),
    )
    with (
        pytest.raises(psycopg.Error, match="already configured"),
        connection.transaction(),
    ):
        configure(connection, other)


@pytest.mark.parametrize("book_db", ["repeatable read"], indirect=True)
def test_setup_rejects_stale_repeatable_read_snapshots(book_db):
    connection, actor = book_db
    with pytest.raises(psycopg.Error, match="READ COMMITTED"), connection.transaction():
        configure(connection, actor)


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": "owner_operations"},
        {"label": "Other"},
        {"reference": "other"},
        {"digest": "b" * 64},
    ],
)
def test_changed_setup_never_relabels_existing_history(book_db, changes):
    connection, actor = book_db
    book_id = configure(connection, actor)
    with (
        pytest.raises(psycopg.Error, match="already configured"),
        connection.transaction(),
    ):
        configure(connection, actor, **changes)
    assert (
        connection.execute("SELECT id FROM accounting.book_identity").fetchone()[0]
        == book_id
    )


@pytest.mark.parametrize("change", ["role", "status", "permission"])
def test_setup_checks_current_management_authority(book_db, change):
    connection, actor = book_db
    if change == "role":
        connection.execute("DELETE FROM core.user_roles WHERE user_id=%s", (actor,))
    elif change == "status":
        connection.execute(
            "UPDATE core.users SET status='inactive' WHERE id=%s", (actor,)
        )
    else:
        connection.execute(
            "DELETE FROM core.role_permissions WHERE permission_code='accounting.journal.manage'"
        )
    with (
        pytest.raises(psycopg.Error, match="active Management"),
        connection.transaction(),
    ):
        configure(connection, actor)
    assert (
        connection.execute("SELECT count(*) FROM accounting.book_identity").fetchone()[
            0
        ]
        == 0
    )


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE accounting.book_identity SET evidence_reference='replacement'",
        "UPDATE accounting.book_identity SET entity_label='replacement'",
        "DELETE FROM accounting.book_identity",
        "TRUNCATE accounting.book_identity",
    ],
)
def test_identity_and_evidence_are_immutable(book_db, statement):
    connection, actor = book_db
    configure(connection, actor)
    with pytest.raises(psycopg.Error, match="immutable"), connection.transaction():
        connection.execute(statement)
    assert (
        connection.execute("SELECT count(*) FROM accounting.book_identity").fetchone()[
            0
        ]
        == 1
    )


@pytest.mark.parametrize(
    "kind,ownership",
    [
        ("synthetic", "synthetic"),
        ("owner_operations", "owner_personal"),
        ("owner_operations", "owner_business"),
        ("corporate_legal", "corporate"),
    ],
)
def test_compatible_context_and_wallet_resolve_exact_book(book_db, kind, ownership):
    connection, actor = book_db
    book_id = configure(connection, actor, kind)
    context_id = context(connection, actor, kind)
    account_id = account(connection, actor, context_id, ownership)
    assert (
        connection.execute(
            "SELECT accounting.require_book_treasury_context(%s)", (context_id,)
        ).fetchone()[0]
        == book_id
    )
    assert (
        connection.execute(
            "SELECT accounting.require_book_treasury_account(%s)", (account_id,)
        ).fetchone()[0]
        == book_id
    )


@pytest.mark.parametrize(
    "kind,other_kind",
    [
        ("owner_operations", "corporate_legal"),
        ("corporate_legal", "owner_operations"),
        ("synthetic", "owner_operations"),
        ("owner_operations", "synthetic"),
    ],
)
def test_cross_book_context_is_rejected(book_db, kind, other_kind):
    connection, actor = book_db
    configure(connection, actor, kind)
    context_id = context(connection, actor, other_kind)
    with pytest.raises(psycopg.Error, match="does not match"), connection.transaction():
        connection.execute(
            "SELECT accounting.require_book_treasury_context(%s)", (context_id,)
        )


@pytest.mark.parametrize("ownership", ["owner_personal", "owner_business", "synthetic"])
def test_personal_or_other_wallet_cannot_be_company_cash(book_db, ownership):
    connection, actor = book_db
    configure(connection, actor, "corporate_legal")
    context_id = context(connection, actor, "corporate_legal")
    account_id = account(connection, actor, context_id, ownership)
    with pytest.raises(psycopg.Error, match="ownership"), connection.transaction():
        connection.execute(
            "SELECT accounting.require_book_treasury_account(%s)", (account_id,)
        )


def test_inactive_and_missing_wallets_are_rejected(book_db):
    connection, actor = book_db
    configure(connection, actor)
    context_id = context(connection, actor, "synthetic")
    account_id = account(connection, actor, context_id, "synthetic", active=False)
    for candidate in (account_id, uuid4()):
        with (
            pytest.raises(psycopg.Error, match="unavailable|inactive"),
            connection.transaction(),
        ):
            connection.execute(
                "SELECT accounting.require_book_treasury_account(%s)", (candidate,)
            )


def test_invalid_evidence_and_direct_insert_cannot_configure_book(book_db):
    connection, actor = book_db
    for changes in (
        {"label": " "},
        {"label": "\t"},
        {"reference": "\n"},
        {"digest": "invalid"},
        {"reference": ""},
        {"kind": "unknown"},
    ):
        with (
            pytest.raises(psycopg.errors.InvalidParameterValue),
            connection.transaction(),
        ):
            configure(connection, actor, **changes)
    with (
        pytest.raises(psycopg.Error, match="protected setup"),
        connection.transaction(),
    ):
        connection.execute(
            """INSERT INTO accounting.book_identity(kind,entity_label,evidence_reference,evidence_digest,configured_by_user_id)
               VALUES('synthetic','Bypass','test','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',%s)""",
            (actor,),
        )


@pytest.mark.parametrize("kind", ["corporate_legal", "synthetic"])
def test_new_book_setup_cannot_relabel_preexisting_wallet_history(book_db, kind):
    connection, actor = book_db
    context_id = context(connection, actor, "owner_operations")
    account(connection, actor, context_id, "owner_personal")
    with (
        pytest.raises(psycopg.Error, match="empty business database"),
        connection.transaction(),
    ):
        configure(connection, actor, kind)


def test_owner_setup_explicitly_adopts_existing_owner_sources(book_db):
    connection, actor = book_db
    context_id = context(connection, actor, "owner_operations")
    wallet = account(connection, actor, context_id, "owner_personal")
    book_id = configure(connection, actor, "owner_operations")
    assert (
        connection.execute(
            "SELECT accounting.require_book_treasury_account(%s)", (wallet,)
        ).fetchone()[0]
        == book_id
    )


def test_unposted_funding_also_prevents_corporate_adoption(book_db):
    connection, actor = book_db
    connection.execute(
        """SELECT accounting.record_initial_capital_funding_evidence(
            %s,%s,'2050-01-01',1,'1010','test','synthetic-funding',%s,'test only')""",
        (actor, uuid4(), "a" * 64),
    )
    with (
        pytest.raises(psycopg.Error, match="empty business database"),
        connection.transaction(),
    ):
        configure(connection, actor, "corporate_legal")


@pytest.mark.parametrize("stage", ["review", "prepared", "closed"])
def test_existing_zero_activity_close_history_prevents_corporate_adoption(
    book_db, stage
):
    from test_period_close_postgres import _move_to_review, _period, _post_close

    connection, actor = book_db
    period, _, end = _period(connection, actor_id=actor, suffix=uuid4().hex)
    _move_to_review(connection, period, actor)
    if stage in {"prepared", "closed"}:
        connection.execute(
            "SELECT accounting.prepare_period_close(%s,%s)", (period, actor)
        )
    if stage == "closed":
        digest = connection.execute(
            "SELECT close_digest FROM accounting.period_close_preparations WHERE fiscal_period_id=%s",
            (period,),
        ).fetchone()[0]
        _post_close(
            connection,
            period_id=period,
            actor_id=actor,
            token="a" * 64,
            close_digest=digest,
            net_income="0.00",
            end_date=end,
        )
    assert (
        connection.execute(
            "SELECT count(*) FROM accounting.journal_entries"
        ).fetchone()[0]
        == 0
    )
    with (
        pytest.raises(psycopg.Error, match="empty business database"),
        connection.transaction(),
    ):
        configure(connection, actor, "corporate_legal")


def test_private_table_and_functions_are_not_granted_to_clients(book_db):
    connection, _ = book_db
    assert connection.execute(
        "SELECT relrowsecurity FROM pg_class WHERE oid='accounting.book_identity'::regclass"
    ).fetchone()[0]
    for role in ("anon", "authenticated", "service_role"):
        if not connection.execute(
            "SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)
        ).fetchone():
            continue
        assert not connection.execute(
            "SELECT has_table_privilege(%s,'accounting.book_identity','SELECT,INSERT,UPDATE,DELETE,TRUNCATE')",
            (role,),
        ).fetchone()[0]
        assert not connection.execute(
            "SELECT has_function_privilege(%s,'accounting.configure_book_identity(text,text,text,text,uuid)','EXECUTE')",
            (role,),
        ).fetchone()[0]


def test_unprivileged_role_cannot_read_or_execute_setup(book_db):
    from psycopg import sql

    connection, actor = book_db
    configure(connection, actor)
    probe = sql.Identifier(f"book_probe_{uuid4().hex}")
    connection.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(probe))
    connection.execute(sql.SQL("GRANT USAGE ON SCHEMA accounting TO {}").format(probe))
    for statement in (
        "SELECT * FROM accounting.book_identity",
        "SELECT accounting.configure_book_identity('synthetic','Unauthorized','test','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',NULL)",
        "SELECT accounting.require_book_treasury_context(NULL)",
        "SELECT accounting.require_book_treasury_account(NULL)",
    ):
        with (
            pytest.raises(psycopg.errors.InsufficientPrivilege),
            connection.transaction(),
        ):
            connection.execute(sql.SQL("SET LOCAL ROLE {}").format(probe))
            connection.execute(statement)


def test_repository_and_same_transaction_context_adapter(book_db, monkeypatch):
    from contextlib import contextmanager

    from psycopg.rows import dict_row

    from gilbic_backend import accounting_book_repository as repository

    connection, actor = book_db

    @contextmanager
    def existing_transaction():
        yield connection

    monkeypatch.setattr(repository, "open_connection", existing_transaction)
    books = repository.PostgresAccountingBookRepository()
    assert books.get_book_identity() is None
    identity = books.configure_book_identity(
        kind="synthetic",
        entity_label="Synthetic repository book",
        evidence_reference="test:repository",
        evidence_digest="a" * 64,
        actor_user_id=actor,
    )
    assert identity.kind == "synthetic"
    assert books.get_book_identity() == identity
    context_id = context(connection, actor, "synthetic")
    wallet_id = account(connection, actor, context_id, "synthetic")
    with connection.cursor(row_factory=dict_row) as cursor:
        assert repository.read_book_identity(cursor) == identity
        assert (
            repository.require_accounting_context(cursor, context_id)
            == identity.book_id
        )
        assert (
            repository.require_accounting_account(cursor, wallet_id) == identity.book_id
        )
    with (
        pytest.raises(repository.AccountingBookConflict, match="already configured"),
        connection.transaction(),
    ):
        books.configure_book_identity(
            kind="owner_operations",
            entity_label="Changed",
            evidence_reference="test:repository",
            evidence_digest="a" * 64,
            actor_user_id=actor,
        )
