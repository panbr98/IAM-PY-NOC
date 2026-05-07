from __future__ import annotations

from pathlib import Path

import httpx

from client_app.desktop_user_ui.api_client import (
    ServerProfileStore,
    build_discovery_candidates,
    discover_server_profiles,
    normalize_api_base_url,
)


def test_normalize_api_base_url_handles_host_and_full_path() -> None:
    assert normalize_api_base_url("127.0.0.1:8787") == "http://127.0.0.1:8787/api/v1"
    assert normalize_api_base_url("http://localhost:8787/") == "http://localhost:8787/api/v1"
    assert normalize_api_base_url("http://server.example/api/v1") == "http://server.example/api/v1"


def test_profile_store_upsert_replaces_matching_name(tmp_path: Path) -> None:
    store = ServerProfileStore(tmp_path / "profiles.json")
    store.save([{"name": "Local", "base_url": "http://127.0.0.1:8787/api/v1", "fingerprint": "A"}])
    profiles = store.upsert(
        {"name": "Local", "base_url": "http://localhost:8787/api/v1", "fingerprint": "B"}
    )
    assert len(profiles) == 1
    assert profiles[0]["fingerprint"] == "B"


def test_build_discovery_candidates_includes_saved_profiles() -> None:
    candidates = build_discovery_candidates(
        [{"name": "Saved", "base_url": "demo.local:8787", "fingerprint": "FP"}]
    )
    assert "http://demo.local:8787/api/v1" in candidates
    assert "http://127.0.0.1:8787/api/v1" in candidates


def test_discover_server_profiles_collects_successes(monkeypatch) -> None:
    def fake_get(url: str, timeout: float):
        if "127.0.0.1" in url:
            request = httpx.Request("GET", url)
            return httpx.Response(
                200,
                request=request,
                json={
                    "product_name": "Noctrix",
                    "environment": "demo",
                    "company_name": "Example Co",
                    "host": "127.0.0.1",
                    "port": 8787,
                    "fingerprint": "DEMO-FP",
                    "health": "ok",
                },
            )
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "get", fake_get)
    profiles = discover_server_profiles(
        ["http://127.0.0.1:8787/api/v1", "http://192.168.1.20:8787/api/v1"]
    )
    assert len(profiles) == 1
    assert profiles[0]["bootstrap_mode"] == "discovery"
    assert profiles[0]["fingerprint"] == "DEMO-FP"
