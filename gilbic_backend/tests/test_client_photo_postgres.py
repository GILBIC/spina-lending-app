from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from threading import Barrier
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from gilbic_backend.auth_api import (
    account_repository_dependency,
    auth_client_dependency,
)
from gilbic_backend.client_photo_api import (
    client_photo_repository_dependency,
    create_client_photo_router,
)
from psycopg.rows import dict_row
from test_client_cif_review_confirmation_postgres import (
    DATABASE_URL,
)
from test_client_cif_review_confirmation_postgres import (
    connection as connection,  # noqa: PLC0414 - pytest fixture import
)
from test_client_cif_review_confirmation_postgres import (
    runtime_url as runtime_url,  # noqa: PLC0414 - pytest fixture import
)
from test_client_photo import picture
from test_client_photo_api import ACTOR, HEADERS, Accounts, Auth

from gilbic_backend import client_photo_repository as module

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="Disposable database required")


def seed(connection):
    user, borrower, collector, client = [uuid4() for _ in range(4)]
    for uid in (user, borrower, collector):
        connection.execute(
            "insert into core.users(id,username,full_name) values(%s,%s,'Synthetic photo actor')",
            (uid, uid.hex),
        )
    connection.execute(
        "insert into lending.clients(id,user_id,client_code,full_name,status,area) values(%s,%s,%s,'Synthetic photo client','active',%s)",
        (client, borrower, client.hex, client.hex),
    )
    connection.execute(
        "insert into lending.collector_area_assignments(collector_user_id,area) values(%s,%s)",
        (collector, client.hex),
    )
    connection.execute(
        "insert into lending.client_cif_versions(client_id,version_number,full_name,phone_number,present_address) values(%s,1,'Synthetic photo client','0000','Test')",
        (client,),
    )
    return (
        client,
        replace(ACTOR, user_id=user),
        replace(ACTOR, user_id=borrower, roles=("client",), permissions=()),
        replace(
            ACTOR, user_id=collector, roles=("collector",), permissions=("route.view",)
        ),
    )


def repository(connection, monkeypatch):
    @contextmanager
    def acquire():
        with connection.transaction():
            yield connection

    monkeypatch.setattr(module, "open_connection", acquire)
    return module.PostgresClientPhotoRepository()


def upload(repo, client, actor, **changes):
    values = {
        "client_id": client,
        "actor": actor,
        "request_id": uuid4(),
        "expected_version": 0,
        "prepared": module.prepare_photo(picture(), "image/png"),
    }
    values.update(changes)
    return repo.upload(**values)


def test_missing_upload_replace_history_and_liveness_unchanged(connection, monkeypatch):
    client, staff, borrower, collector = seed(connection)
    repo = repository(connection, monkeypatch)
    assert repo.get(actor=staff, client_id=client)["photo"] is None
    key = uuid4()
    first = upload(repo, client, staff, request_id=key)
    photo = first["photo"]
    assert photo["version"] == 1
    assert photo["uploaded_by_user_id"] == str(staff.user_id)
    assert upload(repo, client, staff, request_id=key) == first
    for actor in (borrower, collector):
        assert repo.get(actor=actor, client_id=client)["can_upload"] is False
        assert repo.content(
            actor=actor, client_id=client, photo_id=UUID(photo["photo_id"])
        )[0]
    second = upload(
        repo,
        client,
        staff,
        expected_version=1,
        prepared=module.prepare_photo(picture(color="blue"), "image/png"),
    )
    assert second["photo"]["version"] == 2
    assert (
        upload(repo, client, staff, request_id=key) == second
    )  # retry cannot resurrect old version
    with pytest.raises(module.ClientPhotoNotFound):
        repo.content(actor=borrower, client_id=client, photo_id=UUID(photo["photo_id"]))
    assert (
        connection.execute(
            "select count(*) as n from lending.client_photos where client_id=%s",
            (client,),
        ).fetchone()["n"]
        == 2
    )
    assert (
        connection.execute(
            "select count(*) as n from core.audit_logs where target_id=%s and action='client.photo_uploaded'",
            (client,),
        ).fetchone()["n"]
        == 2
    )
    assert connection.execute(
        "select baseline_liveness_status,baseline_face_scan_evidence_reference,status from lending.client_cif_versions where client_id=%s",
        (client,),
    ).fetchone() == {
        "baseline_liveness_status": "pending",
        "baseline_face_scan_evidence_reference": None,
        "status": "draft",
    }


def test_stale_replacement_and_changed_retry_rejected(connection, monkeypatch):
    client, staff, _, _ = seed(connection)
    repo = repository(connection, monkeypatch)
    key = uuid4()
    upload(repo, client, staff, request_id=key)
    with pytest.raises(module.ClientPhotoConflict):
        upload(repo, client, staff)
    with pytest.raises(module.ClientPhotoConflict):
        upload(repo, client, staff, request_id=key, expected_version=1)
    with pytest.raises(module.ClientPhotoConflict):
        upload(
            repo,
            client,
            staff,
            request_id=key,
            prepared=module.prepare_photo(picture(color="blue"), "image/png"),
        )
    assert (
        connection.execute(
            "select count(*) as n from lending.client_photos where client_id=%s",
            (client,),
        ).fetchone()["n"]
        == 1
    )


def test_scope_rechecked_on_every_read_and_upload(connection, monkeypatch):
    client, staff, borrower, collector = seed(connection)
    repo = repository(connection, monkeypatch)
    photo = upload(repo, client, staff)["photo"]
    for actor in (
        replace(borrower, user_id=uuid4()),
        replace(collector, user_id=uuid4()),
        replace(staff, roles=("employee",), permissions=()),
    ):
        with pytest.raises(module.ClientPhotoNotFound):
            repo.get(actor=actor, client_id=client)
        with pytest.raises(module.ClientPhotoNotFound):
            repo.content(
                actor=actor, client_id=client, photo_id=UUID(photo["photo_id"])
            )
    for actor in (collector, borrower):
        with pytest.raises(module.ClientPhotoForbidden):
            upload(repo, client, actor, expected_version=1)
    connection.execute(
        "update lending.collector_area_assignments set is_active=false where collector_user_id=%s",
        (collector.user_id,),
    )
    with pytest.raises(module.ClientPhotoNotFound):
        repo.content(
            actor=collector, client_id=client, photo_id=UUID(photo["photo_id"])
        )


def test_history_is_immutable_and_not_public(connection, monkeypatch):
    client, staff, _, _ = seed(connection)
    repo = repository(connection, monkeypatch)
    upload(repo, client, staff)
    for statement in (
        "delete from lending.client_photos where client_id=%s",
        "update lending.client_photos set version=99 where client_id=%s",
    ):
        with pytest.raises(psycopg.Error), connection.transaction():
            connection.execute(statement, (client,))
    assert connection.execute(
        "select relrowsecurity from pg_class where oid='lending.client_photos'::regclass"
    ).fetchone()["relrowsecurity"]
    assert not connection.execute(
        "select exists(select 1 from pg_class c cross join lateral aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) acl where c.oid='lending.client_photos'::regclass and acl.grantee=0) as public_access"
    ).fetchone()["public_access"]


@pytest.mark.parametrize(
    "same_request", [False, True], ids=["competing-uploads", "identical-retries"]
)
def test_parallel_replacements_have_one_winner(runtime_url, monkeypatch, same_request):
    with psycopg.connect(runtime_url, row_factory=dict_row) as setup:
        client, staff, _, _ = seed(setup)

    @contextmanager
    def acquire():
        with psycopg.connect(runtime_url, row_factory=dict_row) as conn:
            yield conn

    monkeypatch.setattr(module, "open_connection", acquire)
    barrier = Barrier(2)
    request_id = uuid4()

    def attempt(color):
        prepared = module.prepare_photo(
            picture(color="red" if same_request else color), "image/png"
        )
        barrier.wait(timeout=10)
        try:
            return upload(
                module.PostgresClientPhotoRepository(),
                client,
                staff,
                prepared=prepared,
                request_id=request_id if same_request else uuid4(),
            )["photo"]["version"]
        except module.ClientPhotoConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ("red", "blue")))
    assert sorted(map(str, results)) == (
        ["1", "1"] if same_request else ["1", "conflict"]
    )
    with acquire() as conn:
        assert (
            conn.execute(
                "select count(*) as n from lending.client_photos where client_id=%s",
                (client,),
            ).fetchone()["n"]
            == 1
        )
        assert (
            conn.execute(
                "select count(*) as n from core.audit_logs where target_id=%s and action='client.photo_uploaded'",
                (client,),
            ).fetchone()["n"]
            == 1
        )


def test_retry_cannot_be_retargeted_to_another_client(connection, monkeypatch):
    client, staff, _, _ = seed(connection)
    other, _, _, _ = seed(connection)
    repo = repository(connection, monkeypatch)
    key = uuid4()
    upload(repo, client, staff, request_id=key)
    with pytest.raises(module.ClientPhotoConflict):
        upload(repo, other, staff, request_id=key)
    assert repo.get(actor=staff, client_id=other)["photo"] is None


def test_audit_failure_rolls_back_photo_and_same_request_can_retry(
    connection, monkeypatch
):
    client, staff, _, _ = seed(connection)
    repo = repository(connection, monkeypatch)
    key = uuid4()
    connection.execute("""
        create function pg_temp.reject_photo_audit() returns trigger language plpgsql as $$
        begin raise exception 'Synthetic audit failure'; end; $$;
        create trigger synthetic_reject_photo_audit before insert on core.audit_logs
        for each row when (new.action='client.photo_uploaded') execute function pg_temp.reject_photo_audit();
    """)
    with pytest.raises(psycopg.Error, match="Synthetic audit failure"):
        upload(repo, client, staff, request_id=key)
    assert repo.get(actor=staff, client_id=client)["photo"] is None
    connection.execute("drop trigger synthetic_reject_photo_audit on core.audit_logs")
    assert upload(repo, client, staff, request_id=key)["photo"]["version"] == 1


def test_migration_reapply_preserves_history_and_audit(runtime_url):
    migration = (
        Path(__file__).resolve().parents[1] / "sql/0143_add_private_client_photos.sql"
    )
    with psycopg.connect(runtime_url, autocommit=True) as conn:
        query = "select (select count(*) from lending.client_photos),(select count(*) from core.audit_logs)"
        before = conn.execute(query).fetchone()
        conn.execute(migration.read_text())
        assert conn.execute(query).fetchone() == before
        with pytest.raises(psycopg.Error), conn.transaction():
            conn.execute("truncate lending.client_photos")


def test_http_upload_to_database_and_private_download(connection, monkeypatch):
    client_id, staff, borrower, _ = seed(connection)
    repo = repository(connection, monkeypatch)
    accounts = Accounts()
    accounts.actor = staff
    app = FastAPI()
    app.include_router(create_client_photo_router())
    app.dependency_overrides[auth_client_dependency] = lambda: Auth()
    app.dependency_overrides[account_repository_dependency] = lambda: accounts
    app.dependency_overrides[client_photo_repository_dependency] = lambda: repo
    with TestClient(app) as client:
        path = f"/api/v1/clients/{client_id}/photo"
        response = client.post(
            path,
            params={"request_id": str(uuid4()), "expected_version": 0},
            headers={**HEADERS, "Content-Type": "image/png"},
            content=picture(),
        )
        assert response.status_code == 200
        uploaded = response.json()["data"]["photo"]
        accounts.actor = borrower
        metadata = client.get(path, headers=HEADERS).json()["data"]
        assert metadata["can_upload"] is False
        assert metadata["photo"] == uploaded
        image = client.get(uploaded["content_url"], headers=HEADERS)
        assert image.status_code == 200
        assert image.headers["content-type"] == "image/jpeg"
        assert image.headers["cache-control"] == "no-store"
        assert len(image.content) == uploaded["byte_size"]
        assert (
            image.content
            == repo.content(
                actor=borrower, client_id=client_id, photo_id=UUID(uploaded["photo_id"])
            )[0]
        )
