# Registry test suite
from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest
import requests


BASE = "http://localhost:7700"
CLI = f"{BASE}/cli/registry"


def _service_up() -> bool:
    try:
        return requests.get(f"{BASE}/health", timeout=3).status_code == 200
    except requests.RequestException:
        return False


@pytest.fixture(scope="session")
def registry_available():
    if not _service_up():
        pytest.skip("Registry server is not running")


@contextmanager
def _temp_registry():
    with tempfile.TemporaryDirectory() as tmpdir:
        registry_path = Path(tmpdir) / "registry.md"
        registry_path.write_text("# Service Registry\n\n")
        yield registry_path


def test_registry_core_list_and_get(registry_available):
    from registry_agent.core import cmd_get, cmd_list

    with _temp_registry() as tmp:
        result = cmd_list(tmp)
        assert result["total"] == 0
        assert "services" in result

        result = cmd_get("tmf620/catalogmgt", tmp)
        assert "error" in result


def test_registry_core_resolve_and_dependencies(registry_available):
    from registry_agent.core import cmd_register, cmd_resolve, parse_registry

    with _temp_registry() as tmp:
        svc_a = {
            "id": "test/serviceA",
            "url": "http://localhost:9001",
            "cli": "/cli/test/serviceA",
            "handles": "widgets",
            "use_when": "testing widgets",
            "dependencies": "test/serviceB",
            "owner": "test",
            "tags": ["widget"],
        }
        svc_b = {
            "id": "test/serviceB",
            "url": "http://localhost:9002",
            "cli": "/cli/test/serviceB",
            "handles": "gadgets",
            "use_when": "testing gadgets",
            "dependencies": "none",
            "owner": "test",
            "tags": ["gadget"],
        }
        cmd_register(svc_a, tmp)
        cmd_register(svc_b, tmp)
        services = parse_registry(tmp)
        ids = [s["id"] for s in services]
        assert "test/serviceA" in ids
        assert "test/serviceB" in ids
        svc_a_parsed = next(s for s in services if s["id"] == "test/serviceA")
        assert svc_a_parsed.get("dependencies") == "test/serviceB"

        result = cmd_resolve("I need to manage product catalogs", tmp)
        assert "query" in result
        assert "matches" in result
        assert isinstance(result["matches"], list)
        assert "total_services" in result
        assert "returned" in result

        result = cmd_resolve("widgets", tmp)
        assert "matches" in result


def test_registry_core_status_behaviour(registry_available):
    from registry_agent.core import cmd_get, cmd_register, cmd_resolve, cmd_setstatus

    with _temp_registry() as tmp:
        svc = {
            "id": "test/status",
            "url": "http://localhost:9999",
            "cli": "/cli/test/status",
            "handles": "status testing",
            "use_when": "testing",
            "owner": "test",
            "tags": ["test"],
        }
        cmd_register(svc, tmp)
        lst = cmd_get("test/status", tmp)
        assert lst["service"]["status"] == "live"
        r = cmd_setstatus("test/status", "degraded", tmp)
        assert r["status"] == "updated"
        assert r["previous"] == "live"
        assert r["current"] == "degraded"
        got = cmd_get("test/status", tmp)
        assert got["service"]["status"] == "degraded"
        r2 = cmd_setstatus("test/status", "broken", tmp)
        assert "error" in r2
        r3 = cmd_setstatus("test/missing", "live", tmp)
        assert "error" in r3


def test_registry_core_register_preserves_status(registry_available):
    from registry_agent.core import cmd_get, cmd_register, cmd_setstatus

    with _temp_registry() as tmp:
        svc = {
            "id": "test/preserve",
            "url": "http://localhost:9995",
            "cli": "/cli/test/preserve",
            "handles": "preserve testing",
            "use_when": "testing",
            "owner": "test",
            "tags": ["test"],
        }
        cmd_register(svc, tmp)
        cmd_setstatus("test/preserve", "degraded", tmp)
        svc["handles"] = "updated handles"
        cmd_register(svc, tmp)
        got = cmd_get("test/preserve", tmp)
        assert got["service"]["status"] == "degraded"
        svc["status"] = "live"
        cmd_register(svc, tmp)
        got = cmd_get("test/preserve", tmp)
        assert got["service"]["status"] == "live"


def test_registry_core_resolve_includes_status(registry_available):
    from registry_agent.core import cmd_register, cmd_resolve, cmd_setstatus

    with _temp_registry() as tmp:
        svc = {
            "id": "test/resolvestatus",
            "url": "http://localhost:9994",
            "cli": "/cli/test/resolvestatus",
            "handles": "resolve status testing",
            "use_when": "testing",
            "owner": "test",
            "tags": ["test"],
        }
        cmd_register(svc, tmp)
        result = cmd_resolve("resolve status testing", tmp)
        assert result["matches"], "expected at least one match"
        assert result["matches"][0]["status"] == "live"
        cmd_setstatus("test/resolvestatus", "degraded", tmp)
        result = cmd_resolve("resolve status testing", tmp)
        assert result["matches"][0]["status"] == "degraded"


def test_registry_core_register_and_unregister(registry_available):
    from registry_agent.core import cmd_list, cmd_register, cmd_unregister

    with _temp_registry() as tmp:
        svc = {
            "id": "test/svc",
            "url": "http://localhost:9999",
            "cli": "/cli/test/svc",
            "mcp": "http://localhost:9999/mcp",
            "handles": "test stuff",
            "use_when": "testing",
            "owner": "test-team",
            "tags": ["test"],
        }
        reg = cmd_register(svc, tmp)
        assert reg["status"] == "registered"
        lst = cmd_list(tmp)
        assert lst["total"] == 1
        assert lst["services"][0]["id"] == "test/svc"
        svc["handles"] = "updated stuff"
        reg2 = cmd_register(svc, tmp)
        assert reg2["status"] == "updated"
        unreg = cmd_unregister("test/svc", tmp)
        assert unreg["status"] == "unregistered"
        lst2 = cmd_list(tmp)
        assert lst2["total"] == 0


def test_registry_http_health_and_discovery(registry_available):
    r = requests.get(f"{BASE}/health", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"

    r = requests.get(CLI, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["interface"] == "cli"
    assert data["version"] == "1.0"
    assert data["service"] == "registry"
    assert len(data["commands"]) == 6
    names = [c["name"] for c in data["commands"]]
    for expected in ["list", "get", "resolve", "register", "unregister", "setstatus"]:
        assert expected in names, f"Missing command: {expected}"


def test_registry_http_list(registry_available):
    r = requests.post(CLI, json={"command": "list"}, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "services" in data["result"]
    assert data["result"]["total"] >= 1


def test_registry_http_get(registry_available):
    r = requests.post(
        CLI, json={"command": "get", "args": {"service_id": "tmf620/catalogmgt"}}, timeout=30
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["result"]["service"]["id"] == "tmf620/catalogmgt"

    r = requests.post(
        CLI, json={"command": "get", "args": {"service_id": "nonexistent"}}, timeout=30
    )
    assert r.status_code == 200
    data = r.json()
    assert "error" in data["result"]


def test_registry_http_resolve(registry_available):
    r = requests.post(
        CLI,
        json={
            "command": "resolve",
            "args": {"query": "I need to manage product catalogs"},
        },
        timeout=30,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    result = data["result"]
    assert "query" in result
    assert "matches" in result
    assert isinstance(result["matches"], list)
    if "resolved_by" in result:
        assert result["resolved_by"] in ("opencode-agent", "fallback")
    assert "reference_suggestions" in result
    assert isinstance(result["reference_suggestions"], list)
    assert "related_services" in result
    assert isinstance(result["related_services"], list)
    if result["matches"]:
        first = result["matches"][0]
        if "tmf_validation" in first:
            assert isinstance(first["tmf_validation"], dict)
            assert "validated" in first["tmf_validation"]


def test_registry_http_resolve_prerequisites_and_registry_dump(registry_available):
    r = requests.post(
        CLI,
        json={
            "command": "resolve",
            "args": {"query": "I need to manage product catalogs"},
        },
        timeout=30,
    )
    assert r.status_code == 200
    result = r.json()["result"]
    resolved_by = result.get("resolved_by")
    if result.get("matches") and resolved_by is None:
        for match in result.get("matches", []):
            if "tmf_validation" in match:
                assert "tmf_api_id" in match["tmf_validation"]
                assert "validated" in match["tmf_validation"]
        assert "registry_content" not in result
    elif resolved_by == "opencode-agent":
        for match in result.get("matches", []):
            assert "prerequisites" in match
            assert isinstance(match["prerequisites"], list)
            for prereq in match["prerequisites"]:
                assert "id" in prereq
                assert "note" in prereq
            if "tmf_validation" in match:
                assert "tmf_api_id" in match["tmf_validation"]
                assert "validated" in match["tmf_validation"]
        assert "registry_content" not in result


def test_registry_http_lifecycle(registry_available):
    svc = {
        "id": "test/lifecycle",
        "url": "http://localhost:9998",
        "cli": "/cli/test/lifecycle",
        "mcp": "http://localhost:9998/mcp",
        "handles": "test lifecycle",
        "use_when": "testing register/unregister",
        "owner": "test-team",
        "tags": ["test", "lifecycle"],
    }
    r = requests.post(CLI, json={"command": "register", "args": {"body": svc}}, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["result"]["status"] in ("registered", "updated")

    r = requests.post(CLI, json={"command": "list"}, timeout=30)
    ids = [s["id"] for s in r.json()["result"]["services"]]
    assert "test/lifecycle" in ids

    r = requests.post(
        CLI, json={"command": "get", "args": {"service_id": "test/lifecycle"}}, timeout=30
    )
    assert r.json()["result"]["service"]["id"] == "test/lifecycle"

    r = requests.post(
        CLI,
        json={"command": "unregister", "args": {"service_id": "test/lifecycle"}},
        timeout=30,
    )
    assert r.json()["result"]["status"] == "unregistered"

    r = requests.post(
        CLI, json={"command": "get", "args": {"service_id": "test/lifecycle"}}, timeout=30
    )
    assert "error" in r.json()["result"]


def test_registry_http_setstatus(registry_available):
    svc = {
        "id": "test/statushttp",
        "url": "http://localhost:9996",
        "cli": "/cli/test/statushttp",
        "handles": "http status testing",
        "use_when": "testing",
        "owner": "test",
        "tags": ["test"],
    }
    requests.post(CLI, json={"command": "register", "args": {"body": svc}}, timeout=30)

    r = requests.post(
        CLI,
        json={
            "command": "setstatus",
            "args": {"service_id": "test/statushttp", "status": "maintenance"},
        },
        timeout=30,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["result"]["current"] == "maintenance"
    assert data["result"]["previous"] == "live"

    r = requests.post(CLI, json={"command": "list"}, timeout=30)
    entries = {s["id"]: s for s in r.json()["result"]["services"]}
    assert entries["test/statushttp"]["status"] == "maintenance"

    r = requests.post(
        CLI,
        json={
            "command": "setstatus",
            "args": {"service_id": "test/statushttp", "status": "broken"},
        },
        timeout=30,
    )
    assert r.status_code == 200
    assert "error" in r.json()["result"]

    requests.post(
        CLI,
        json={"command": "unregister", "args": {"service_id": "test/statushttp"}},
        timeout=30,
    )


def test_registry_http_update(registry_available):
    svc = {
        "id": "test/update",
        "url": "http://localhost:9997",
        "cli": "/cli/test/update",
        "mcp": "http://localhost:9997/mcp",
        "handles": "original",
        "use_when": "testing",
        "owner": "test",
        "tags": ["test"],
    }
    requests.post(CLI, json={"command": "register", "args": {"body": svc}}, timeout=30)
    svc["handles"] = "updated"
    r = requests.post(CLI, json={"command": "register", "args": {"body": svc}}, timeout=30)
    assert r.json()["result"]["status"] == "updated"
    r = requests.post(
        CLI, json={"command": "get", "args": {"service_id": "test/update"}}, timeout=30
    )
    assert r.json()["result"]["service"]["handles"] == "updated"
    requests.post(
        CLI, json={"command": "unregister", "args": {"service_id": "test/update"}}, timeout=30
    )


def test_registry_http_error_handling(registry_available):
    r = requests.post(
        CLI, data="not json", headers={"Content-Type": "application/json"}, timeout=30
    )
    assert r.status_code == 400
    data = r.json()
    assert data["error"]["code"] == "invalid_json"

    r = requests.post(CLI, json={}, timeout=30)
    assert r.status_code == 400
    data = r.json()
    assert data["error"]["code"] == "invalid_command"

    r = requests.post(CLI, json={"command": "bogus"}, timeout=30)
    assert r.status_code == 404
    data = r.json()
    assert data["error"]["code"] == "command_not_found"

    r = requests.post(CLI, json={"command": "get"}, timeout=30)
    assert r.status_code == 400
    data = r.json()
    assert data["error"]["code"] == "missing_required_argument"

    r = requests.post(
        CLI, json={"command": "register", "args": {"body": {"url": "http://x"}}}, timeout=30
    )
    assert r.status_code == 200
    data = r.json()
    assert "error" in data["result"]

    payloads = [
        ("invalid_json", "not json"),
        ("invalid_command", {}),
        ("command_not_found", {"command": "bogus"}),
        ("missing_required_argument", {"command": "get"}),
    ]
    for label, body in payloads:
        if isinstance(body, str):
            r = requests.post(
                CLI, data=body, headers={"Content-Type": "application/json"}, timeout=30
            )
        else:
            r = requests.post(CLI, json=body, timeout=30)
        data = r.json()
        assert data.get("interface") == "cli", label
        assert data.get("version") == "1.0", label
