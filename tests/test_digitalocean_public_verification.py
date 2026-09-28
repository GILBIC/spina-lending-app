"""Synthetic HTTPS responses only; never connect to a deployment target."""

import importlib.util
import json
from email.message import Message
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from urllib.request import HTTPHandler, HTTPSHandler, build_opener
from urllib.response import addinfourl

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "spina_public_deploy", ROOT / "ops/digitalocean/workflow_helper.py"
)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


@pytest.mark.parametrize(
    "destination", ["http://spina.com.ph/", "https://unlisted.example/"]
)
def test_redirect_is_rejected_before_contacting_an_unsafe_intermediate_host(
    destination,
):
    calls = []

    def response(request):
        calls.append(request.full_url)
        headers = Message()
        headers["Location"] = (
            destination if len(calls) == 1 else "https://spina.com.ph/"
        )
        result = addinfourl(BytesIO(b""), headers, request.full_url, 302)
        result.msg = "Found"
        return result

    class Https(HTTPSHandler):
        https_open = staticmethod(response)

    class Http(HTTPHandler):
        http_open = staticmethod(response)

    opener = build_opener(
        Https(), Http(), helper.DeclaredHttpsRedirects({"spina.com.ph"})
    )
    with pytest.raises(ValueError, match="redirect"):
        opener.open("https://spina.com.ph/", timeout=15)
    assert calls == ["https://spina.com.ph/"]


def test_canonical_redirect_within_declared_https_hosts_is_supported():
    calls = []

    class Https(HTTPSHandler):
        def https_open(self, request):
            calls.append(request.full_url)
            headers = Message()
            headers["Location"] = "https://spina.com.ph/"
            result = addinfourl(
                BytesIO(b"portal"),
                headers,
                request.full_url,
                302 if len(calls) == 1 else 200,
            )
            result.msg = "Found" if len(calls) == 1 else "OK"
            return result

    opener = build_opener(
        Https(), helper.DeclaredHttpsRedirects({"www.spina.com.ph", "spina.com.ph"})
    )
    with opener.open("https://www.spina.com.ph/", timeout=15) as response:
        assert response.read() == b"portal"
    assert calls == ["https://www.spina.com.ph/", "https://spina.com.ph/"]


@pytest.fixture
def target(tmp_path):
    path = tmp_path / "target.json"
    path.write_text(
        json.dumps(
            {
                "run_id": 1,
                "droplet_id": 2,
                "host": "159.223.39.43",
                "hostname": "spina.com.ph",
                "aliases": [
                    "app.spina.com.ph",
                    "api.spina.com.ph",
                    "www.spina.com.ph",
                    "spina.159-223-39-43.sslip.io",
                ],
                "cors_origins": ["https://app.spina.com.ph"],
                "staff_invite_redirect_url": "https://app.spina.com.ph/",
            }
        )
    )
    return path


class Response:
    status = 200

    def __init__(self, url, data):
        self.url, self.data = url, data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self):
        return self.url

    def read(self, size=-1):
        return self.data[:size] if size >= 0 else self.data


def network(calls, *, fail=None):
    def get(url, timeout):
        calls.append((url, timeout))
        if url == fail:
            raise OSError("Synthetic domain unavailable")
        body = (
            b'{"status":"ok"}'
            if url.endswith("/health/live")
            else b'{"status":"ready","database":"ok"}'
            if url.endswith("/health/ready")
            else b'<title>Spina Lending Company</title><form id="login-form"></form>'
        )
        return Response(url, body)

    return get


def mock_transport(monkeypatch, get):
    monkeypatch.setattr(
        helper, "build_opener", lambda *handlers: SimpleNamespace(open=get)
    )


def test_every_declared_domain_gets_https_liveness_readiness_and_portal_checks(
    monkeypatch, target, tmp_path
):
    calls = []
    mock_transport(monkeypatch, network(calls))
    output = tmp_path / "checks.json"
    helper.verify_public(target_path=target, output_path=output)
    domains = ["spina.com.ph", *json.loads(target.read_text())["aliases"]]
    assert [url for url, _ in calls] == [
        f"https://{host}{path}"
        for host in domains
        for path in ["/health/live", "/health/ready", "/"]
    ]
    assert all(timeout == 15 for _, timeout in calls)
    assert set(json.loads(output.read_text())["domains"]) == set(domains)


def test_broken_alias_cannot_publish_success_or_reuse_prior_checks(
    monkeypatch, target, tmp_path
):
    calls = []
    mock_transport(
        monkeypatch, network(calls, fail="https://api.spina.com.ph/health/ready")
    )
    output = tmp_path / "checks.json"
    output.write_text('{"domains":{"spina.com.ph":{"database":"ok"}}}')
    with pytest.raises((ValueError, OSError)):
        helper.verify_public(target_path=target, output_path=output)
    assert not output.exists()


@pytest.mark.parametrize("broken", ["database", "portal", "redirect"])
def test_incorrect_response_or_insecure_redirect_fails_closed(
    monkeypatch, target, tmp_path, broken
):
    get = network([])

    def response(url, timeout):
        item = get(url, timeout)
        if broken == "database" and url.endswith("/health/ready"):
            item.data = b'{"status":"ready","database":"down"}'
        if broken == "portal" and url.endswith("/"):
            item.data = b"<title>Another application</title>"
        if broken == "redirect":
            item.url = url.replace("https:", "http:")
        return item

    mock_transport(monkeypatch, response)
    with pytest.raises(ValueError):
        helper.verify_public(target_path=target, output_path=tmp_path / "checks.json")


def test_evidence_requires_complete_current_domain_checks(
    monkeypatch, target, tmp_path
):
    mock_transport(monkeypatch, network([]))
    checks = tmp_path / "checks.json"
    helper.verify_public(target_path=target, output_path=checks)
    evidence = tmp_path / "evidence.json"
    helper.write_evidence(
        target_path=target,
        public_checks_path=checks,
        output_path=evidence,
        git_sha="a" * 40,
        verified_active_sha="a" * 40,
    )
    assert len(json.loads(evidence.read_text())["domains"]) == 5
    payload = json.loads(checks.read_text())
    del payload["domains"]["api.spina.com.ph"]
    checks.write_text(json.dumps(payload))
    evidence.unlink()
    with pytest.raises(ValueError):
        helper.write_evidence(
            target_path=target,
            public_checks_path=checks,
            output_path=evidence,
            git_sha="a" * 40,
            verified_active_sha="a" * 40,
        )
    assert not evidence.exists()
