from fastapi.testclient import TestClient
from gilbic_backend.main import create_app


def test_portal_payment_proof_preflight_allows_private_note_header():
    response = TestClient(create_app()).options(
        "/api/v1/client/payment-proofs",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,x-device-id,x-proof-note",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "x-proof-note" in response.headers["access-control-allow-headers"].lower()


def test_portal_handover_photo_preflight_allows_filename_header():
    response = TestClient(create_app()).options(
        "/api/v1/collector/renewals/00000000-0000-0000-0000-000000000001/handover-photo",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,x-device-id,x-file-name",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "x-file-name" in response.headers["access-control-allow-headers"].lower()
