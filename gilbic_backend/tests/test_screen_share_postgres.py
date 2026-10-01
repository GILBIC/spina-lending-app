"""Atomic device readiness/revocation checks; only the disposable financial runner supplies DSN."""

import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from uuid import uuid4

import psycopg
import pytest
from gilbic_backend.account_repository import AccountContext
from test_screen_share import png

DSN = os.environ.get("GILBIC_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="Disposable PostgreSQL required")


@pytest.fixture
def case(monkeypatch):
    from gilbic_backend.screen_share_frames import FrameCache

    from gilbic_backend import screen_share_repository as module

    actors = []

    @contextmanager
    def connect():
        with psycopg.connect(DSN) as connection:
            yield connection

    monkeypatch.setattr(module, "open_connection", connect)
    with psycopg.connect(DSN) as connection:
        for role in (
            "management",
            "client",
            "management",
            "client",
            "management",
            "client",
        ):
            uid, did = uuid4(), uuid4()
            connection.execute(
                "INSERT INTO core.users(id,username,full_name,status) VALUES(%s,%s,'Synthetic share','active')",
                (uid, str(uid)),
            )
            connection.execute(
                "INSERT INTO core.user_roles(user_id,role_id) SELECT %s,id FROM core.roles WHERE code=%s",
                (uid, role),
            )
            connection.execute(
                "INSERT INTO core.devices(id,user_id,device_identifier_hash,platform,status) VALUES(%s,%s,%s,'web','active')",
                (did, uid, did.hex),
            )
            actors.append(
                AccountContext(
                    uid,
                    uuid4(),
                    str(uid),
                    None,
                    "Synthetic share",
                    "active",
                    (role,),
                    ("screen_share.view",),
                    True,
                    did,
                )
            )
    cache = FrameCache()
    repo = module.PostgresScreenShareRepository(cache=cache)
    try:
        yield repo, actors, connect
    finally:
        cache.close()
        with psycopg.connect(DSN) as connection:
            ids = [a.user_id for a in actors]
            connection.execute(
                "DELETE FROM core.audit_logs WHERE actor_user_id=ANY(%s)", (ids,)
            )
            connection.execute(
                "DELETE FROM core.screen_share_sessions WHERE viewer_user_id=ANY(%s) OR holder_user_id=ANY(%s)",
                (ids, ids),
            )
            connection.execute("DELETE FROM core.devices WHERE user_id=ANY(%s)", (ids,))
            connection.execute(
                "DELETE FROM core.user_roles WHERE user_id=ANY(%s)", (ids,)
            )
            connection.execute("DELETE FROM core.users WHERE id=ANY(%s)", (ids,))


def requested(repo, viewer, holder):
    return repo.request(viewer, holder.user_id, holder.registered_device_id)


def test_device_readiness_exact_device_stop_and_late_frame(case):
    from gilbic_backend.screen_share_frames import ScreenShareError

    repo, a, _ = case
    s = requested(repo, a[0], a[1])
    sid = s["id"]
    with pytest.raises(ScreenShareError) as e:
        repo.upload(a[1], sid, 1, 1, png())
    assert e.value.status_code == 409
    with pytest.raises(ScreenShareError) as e:
        repo.ready(a[3], sid, 1)
    assert e.value.status_code == 404
    with pytest.raises(ScreenShareError) as viewer_ready:
        repo.ready(a[0], sid, 1)
    assert viewer_ready.value.status_code == 404
    with pytest.raises(ScreenShareError) as old_generation:
        repo.ready(a[1], sid, 2)
    assert old_generation.value.status_code == 409
    with pytest.raises(ScreenShareError) as waiting:
        repo.frame(a[0], sid)
    assert waiting.value.status_code == 409
    assert repo.ready(a[1], sid, 1)["state"] == "active"
    repo.upload(a[1], sid, 1, 1, png())
    assert repo.frame(a[0], sid).data == png()
    ended = repo.stop(a[1], sid, 1)
    assert ended["generation"] == 2 and ended["state"] == "stopped"
    assert repo.stop(a[1], sid, 1)["generation"] == 2
    with pytest.raises(ScreenShareError):
        repo.upload(a[1], sid, 1, 2, png())
    assert repo.cache.retained_bytes == 0


def test_current_holder_device_revocation_ends_access(case):
    from gilbic_backend.screen_share_frames import ScreenShareError

    repo, a, connect = case
    s = requested(repo, a[0], a[1])
    repo.ready(a[1], s["id"], 1)
    repo.upload(a[1], s["id"], 1, 1, png())
    with connect() as c:
        c.execute(
            "UPDATE core.devices SET status='revoked' WHERE id=%s",
            (a[1].registered_device_id,),
        )
    with pytest.raises(ScreenShareError) as e:
        repo.frame(a[0], s["id"])
    assert e.value.status_code == 403 and repo.cache.retained_bytes == 0
    with connect() as c:
        assert c.execute(
            "SELECT state,ended_reason FROM core.screen_share_sessions WHERE id=%s",
            (s["id"],),
        ).fetchone() == ("stopped", "authorization_revoked")


def test_role_removal_and_restart_cannot_resurrect_device_readiness(case):
    from gilbic_backend.screen_share_frames import FrameCache, ScreenShareError
    from gilbic_backend.screen_share_repository import PostgresScreenShareRepository

    repo, a, connect = case
    s = requested(repo, a[0], a[1])
    repo.ready(a[1], s["id"], 1)
    with connect() as c:
        c.execute("DELETE FROM core.user_roles WHERE user_id=%s", (a[0].user_id,))
    with pytest.raises(ScreenShareError):
        repo.status(a[1], s["id"])
    s = requested(repo, a[2], a[3])
    repo.ready(a[3], s["id"], 1)
    cache = FrameCache()
    try:
        restarted = PostgresScreenShareRepository(cache=cache)
        assert restarted.status(a[2], s["id"])["state"] == "expired"
    finally:
        cache.close()


def test_expiry_rate_and_two_active_limit(case):
    from gilbic_backend.screen_share_frames import ScreenShareError

    repo, a, connect = case
    for v, h in [(a[0], a[1]), (a[2], a[3])]:
        s = requested(repo, v, h)
        repo.ready(h, s["id"], 1)
    third = requested(repo, a[4], a[5])
    with pytest.raises(ScreenShareError) as e:
        repo.ready(a[5], third["id"], 1)
    assert e.value.status_code == 429
    with connect() as c:
        c.execute(
            "UPDATE core.screen_share_sessions SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE viewer_user_id=%s",
            (a[0].user_id,),
        )
    assert repo.ready(a[5], third["id"], 1)["state"] == "active"
    repo.upload(a[5], third["id"], 1, 1, png())
    with pytest.raises(ScreenShareError) as e:
        repo.upload(a[5], third["id"], 1, 2, png())
    assert e.value.status_code == 429
    with pytest.raises(ScreenShareError) as e:
        repo.upload(a[5], third["id"], 1, 1, png())
    assert e.value.status_code == 409


def test_racing_ready_has_one_transition_and_stop_clears_frame(case):
    from gilbic_backend.screen_share_frames import ScreenShareError

    repo, a, _ = case
    s = requested(repo, a[0], a[1])

    def ready():
        try:
            return repo.ready(a[1], s["id"], 1)["state"]
        except ScreenShareError as e:
            return e.status_code

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: ready(), range(2)))
    assert sorted(map(str, results)) == ["409", "active"]

    def upload():
        try:
            repo.upload(a[1], s["id"], 1, 1, png())
        except ScreenShareError:
            pass

    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(upload), pool.submit(repo.stop, a[0], s["id"], 1)]
        for f in futures:
            f.result()
    assert repo.cache.retained_bytes == 0


def test_same_user_different_device_cannot_ready_or_read(case):
    from dataclasses import replace

    from gilbic_backend.screen_share_frames import ScreenShareError

    repo, a, _ = case
    s = requested(repo, a[0], a[1])
    for actor, action in [
        (replace(a[1], registered_device_id=uuid4()), repo.ready),
        (replace(a[0], registered_device_id=uuid4()), repo.stop),
    ]:
        with pytest.raises(ScreenShareError) as error:
            action(actor, s["id"], 1)
        assert error.value.status_code == 404


@pytest.mark.parametrize("party", [0, 1])
def test_disabled_participant_ends_grant(case, party):
    from gilbic_backend.screen_share_frames import ScreenShareError

    repo, a, connect = case
    s = requested(repo, a[0], a[1])
    repo.ready(a[1], s["id"], 1)
    repo.upload(a[1], s["id"], 1, 1, png())
    with connect() as c:
        c.execute(
            "UPDATE core.users SET status='inactive' WHERE id=%s", (a[party].user_id,)
        )
    with pytest.raises(ScreenShareError) as error:
        repo.frame(a[0], s["id"])
    assert error.value.status_code == 403 and repo.cache.retained_bytes == 0


def test_removed_view_permission_ends_grant(case):
    from gilbic_backend.screen_share_frames import ScreenShareError

    repo, a, connect = case
    s = requested(repo, a[0], a[1])
    repo.ready(a[1], s["id"], 1)
    # Roll back global permission change even if assertion fails.
    with connect() as c:
        c.execute(
            "DELETE FROM core.role_permissions WHERE permission_code='screen_share.view'"
        )
    try:
        with pytest.raises(ScreenShareError) as error:
            repo.status(a[1], s["id"])
        assert error.value.status_code == 403
    finally:
        with connect() as c:
            c.execute(
                "INSERT INTO core.role_permissions(role_id,permission_code) SELECT id,'screen_share.view' FROM core.roles WHERE code='management' ON CONFLICT DO NOTHING"
            )


def test_request_rate_decline_and_pending_expiry(case):
    from gilbic_backend.screen_share_frames import ScreenShareError

    repo, a, connect = case
    s = requested(repo, a[0], a[1])
    assert repo.pending(a[1])["sessions"][0]["id"] == s["id"]
    assert repo.decline(a[1], s["id"], 1)["state"] == "declined"
    s = requested(repo, a[0], a[1])
    with connect() as c:
        c.execute(
            "UPDATE core.screen_share_sessions SET expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
            (s["id"],),
        )
    with pytest.raises(ScreenShareError):
        repo.ready(a[1], s["id"], 1)
    assert repo.status(a[0], s["id"])["state"] == "expired"
    s = requested(repo, a[0], a[1])
    repo.decline(a[1], s["id"], 1)
    with pytest.raises(ScreenShareError) as error:
        requested(repo, a[0], a[1])
    assert error.value.status_code == 429


def test_sql_client_roles_cannot_read_session_metadata(case):
    _, _, connect = case
    with connect() as c:
        for role in ("anon", "authenticated", "service_role"):
            if not c.execute(
                "SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=%s)", (role,)
            ).fetchone()[0]:
                c.execute(
                    psycopg.sql.SQL("CREATE ROLE {} NOLOGIN").format(
                        psycopg.sql.Identifier(role)
                    )
                )
            assert not c.execute(
                "SELECT has_table_privilege(%s,'core.screen_share_sessions','SELECT')",
                (role,),
            ).fetchone()[0]
            with pytest.raises(psycopg.errors.InsufficientPrivilege), c.transaction():
                c.execute(
                    psycopg.sql.SQL("SET LOCAL ROLE {}").format(
                        psycopg.sql.Identifier(role)
                    )
                )
                c.execute("SELECT * FROM core.screen_share_sessions")
        c.rollback()  # Any missing synthetic cluster roles are transaction-local.


def test_failed_commit_never_publishes_a_frame(case, monkeypatch):
    from gilbic_backend import screen_share_repository as module

    repo, a, connect = case
    s = requested(repo, a[0], a[1])
    repo.ready(a[1], s["id"], 1)

    @contextmanager
    def fail_commit():
        with connect() as c:
            c.execute("BEGIN")
            yield c
            c.rollback()
            raise RuntimeError("Synthetic commit failure")

    monkeypatch.setattr(module, "open_connection", fail_commit)
    with pytest.raises(RuntimeError):
        repo.upload(a[1], s["id"], 1, 1, png())
    assert repo.cache.retained_bytes == 0


def test_targets_disambiguate_registered_devices_by_recent_activity(case):
    repo, actors, connect = case
    with connect() as c:
        c.execute(
            "UPDATE core.devices SET last_seen_at='2026-01-02 03:04:05+00' WHERE id=%s",
            (actors[1].registered_device_id,),
        )
    target = next(
        t
        for t in repo.targets(actors[0])["targets"]
        if t["device_id"] == actors[1].registered_device_id
    )
    assert target["device_name"] == "web · last seen 2026-01-02 03:04:05 UTC"
    assert actors[1].registered_device_id.hex not in target["device_name"]


@pytest.mark.parametrize("terminal", ["stopped", "declined", "expired"])
def test_terminal_request_cannot_automatically_become_ready(case, terminal):
    from gilbic_backend.screen_share_frames import ScreenShareError

    repo, actors, connect = case
    request = requested(repo, actors[0], actors[1])
    sid = request["id"]
    if terminal == "stopped":
        ended = repo.stop(actors[0], sid, 1)
    elif terminal == "declined":
        ended = repo.decline(actors[1], sid, 1)
    else:
        with connect() as connection:
            connection.execute(
                "UPDATE core.screen_share_sessions SET expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
                (sid,),
            )
        ended = repo.status(actors[0], sid)
    assert ended["state"] == terminal
    for generation in (1, ended["generation"]):
        with pytest.raises(ScreenShareError) as failure:
            repo.ready(actors[1], sid, generation)
        assert failure.value.status_code == 409
    assert repo.status(actors[0], sid)["state"] == terminal
    assert repo.cache.retained_bytes == 0
