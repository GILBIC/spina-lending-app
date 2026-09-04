from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "ops" / "digitalocean" / "bootstrap.sh"


def test_caddy_transport_matches_host_firewall() -> None:
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    caddy_h1_h2_only = re.search(r"^\s*protocols\s+h1\s+h2\s*$", bootstrap, re.MULTILINE)
    udp_443_open = "ufw allow 443/udp" in bootstrap

    assert caddy_h1_h2_only or udp_443_open, (
        "Caddy defaults to HTTP/3, but the host firewall only opens 443/tcp. "
        "Either constrain Caddy to h1/h2 or explicitly allow 443/udp."
    )
