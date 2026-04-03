# Registry test suite
import json
import sys
import tempfile
import shutil
from pathlib import Path
import requests

BASE = "http://localhost:7700"
CLI = f"{BASE}/cli/registry"
passed = 0
failed = 0
errors = []


def test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  PASS  {name}")
    except Exception as exc:
        failed += 1
        errors.append((name, str(exc)))
        print(f"  FAIL  {name}: {exc}")


def core_list():
    from registry_core import cmd_list

    result = cmd_list()
    assert result["total"] >= 1
    assert "services" in result


def core_get():
    from registry_core import cmd_get

    result = cmd_get("tmf620/catalogmgt")
    assert "service" in result
    assert result["service"]["id"] == "tmf620/catalogmgt"


def core_get_not_found():
    from registry_core import cmd_get

    result = cmd_get("nonexistent")
    assert "error" in result


def core_resolve():
    from registry_core import cmd_resolve

    result = cmd_resolve("I need to manage product catalogs")
    assert "query" in result
    assert "matches" in result
    assert isinstance(result["matches"], list)
    assert "total_services" in result
    assert "returned" in result


def core_resolve_dependencies():
    from registry_core import cmd_register, cmd_resolve, cmd_unregister, parse_registry

    tmp = Path(tempfile.mkdtemp()) / "registry.md"
    tmp.write_text("# Service Registry\n\n")
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
    result = cmd_resolve("widgets", tmp)
    assert "matches" in result
    shutil.rmtree(tmp.parent)


def core_setstatus():
    from registry_core import cmd_register, cmd_setstatus, cmd_get, cmd_list

    tmp = Path(tempfile.mkdtemp()) / "registry.md"
    tmp.write_text("# Service Registry\n\n")
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

    # default status is "live" in list
    lst = cmd_list(tmp)
    assert lst["services"][0]["status"] == "live"

    # set to degraded
    r = cmd_setstatus("test/status", "degraded", tmp)
    assert r["status"] == "updated"
    assert r["previous"] == "live"
    assert r["current"] == "degraded"

    # persisted in get
    got = cmd_get("test/status", tmp)
    assert got["service"]["status"] == "degraded"

    # invalid status rejected
    r2 = cmd_setstatus("test/status", "broken", tmp)
    assert "error" in r2

    # not found
    r3 = cmd_setstatus("test/missing", "live", tmp)
    assert "error" in r3

    shutil.rmtree(tmp.parent)


def core_register_preserves_status():
    from registry_core import cmd_register, cmd_setstatus, cmd_get

    tmp = Path(tempfile.mkdtemp()) / "registry.md"
    tmp.write_text("# Service Registry\n\n")
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

    # update metadata without status field — status must survive
    svc["handles"] = "updated handles"
    cmd_register(svc, tmp)
    got = cmd_get("test/preserve", tmp)
    assert got["service"]["status"] == "degraded", (
        "register must not reset status when caller omits it"
    )

    # explicit status in payload overrides
    svc["status"] = "live"
    cmd_register(svc, tmp)
    got = cmd_get("test/preserve", tmp)
    assert got["service"]["status"] == "live"

    shutil.rmtree(tmp.parent)


def core_resolve_includes_status():
    from registry_core import cmd_register, cmd_setstatus, cmd_resolve

    tmp = Path(tempfile.mkdtemp()) / "registry.md"
    tmp.write_text("# Service Registry\n\n")
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

    # no explicit status — should default to live in resolve
    result = cmd_resolve("resolve status testing", tmp)
    assert result["matches"], "expected at least one match"
    assert result["matches"][0]["status"] == "live", (
        "resolve must default status to live when absent"
    )

    # set degraded — must appear in resolve
    cmd_setstatus("test/resolvestatus", "degraded", tmp)
    result = cmd_resolve("resolve status testing", tmp)
    assert result["matches"][0]["status"] == "degraded", (
        "resolve must surface current status"
    )

    shutil.rmtree(tmp.parent)


def core_register_and_unregister():
    from registry_core import cmd_register, cmd_unregister, cmd_list

    tmp = Path(tempfile.mkdtemp()) / "registry.md"
    tmp.write_text("# Service Registry\n\n")
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
    shutil.rmtree(tmp.parent)


def http_health():
    r = requests.get(f"{BASE}/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"


def http_discovery():
    r = requests.get(CLI)
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


def http_list():
    r = requests.post(CLI, json={"command": "list"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "services" in data["result"]
    assert data["result"]["total"] >= 1


def http_get():
    r = requests.post(
        CLI, json={"command": "get", "args": {"service_id": "tmf620/catalogmgt"}}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["result"]["service"]["id"] == "tmf620/catalogmgt"


def http_get_not_found():
    r = requests.post(
        CLI, json={"command": "get", "args": {"service_id": "nonexistent"}}
    )
    assert r.status_code == 200
    data = r.json()
    assert "error" in data["result"]


def http_resolve():
    r = requests.post(
        CLI,
        json={
            "command": "resolve",
            "args": {"query": "I need to manage product catalogs"},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    result = data["result"]
    assert "query" in result
    assert "matches" in result
    assert isinstance(result["matches"], list)
    assert "resolved_by" in result
    assert result["resolved_by"] in ("opencode", "fallback")


def http_resolve_prerequisites_shape():
    """prerequisites shape is gated on resolved_by.

    opencode path: each match has prerequisites list; each entry has id and note.
    fallback path: prerequisites is absent — not synthesized without LLM.
    """
    r = requests.post(
        CLI,
        json={
            "command": "resolve",
            "args": {"query": "I need to manage product catalogs"},
        },
    )
    assert r.status_code == 200
    result = r.json()["result"]
    resolved_by = result.get("resolved_by")

    if resolved_by == "opencode":
        for match in result.get("matches", []):
            assert "prerequisites" in match, (
                f"opencode match missing prerequisites: {match.get('id')}"
            )
            assert isinstance(match["prerequisites"], list)
            for prereq in match["prerequisites"]:
                assert "id" in prereq, f"prerequisite missing 'id': {prereq}"
                assert "note" in prereq, f"prerequisite missing 'note': {prereq}"
    elif resolved_by == "fallback":
        for match in result.get("matches", []):
            assert "prerequisites" not in match, (
                f"fallback must not synthesize prerequisites: {match.get('id')}"
            )


def http_resolve_no_registry_dump():
    """Resolve must never return registry_content unless explicitly requested via fallback."""
    r = requests.post(
        CLI,
        json={
            "command": "resolve",
            "args": {"query": "I need to manage product catalogs"},
        },
    )
    result = r.json()["result"]
    if result.get("resolved_by") == "opencode":
        assert "registry_content" not in result, (
            "LLM path must not return full registry_content"
        )


def http_register_and_unregister():
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
    r = requests.post(CLI, json={"command": "register", "args": {"body": svc}})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["result"]["status"] in ("registered", "updated")
    r = requests.post(CLI, json={"command": "list"})
    ids = [s["id"] for s in r.json()["result"]["services"]]
    assert "test/lifecycle" in ids
    r = requests.post(
        CLI, json={"command": "get", "args": {"service_id": "test/lifecycle"}}
    )
    assert r.json()["result"]["service"]["id"] == "test/lifecycle"
    r = requests.post(
        CLI, json={"command": "unregister", "args": {"service_id": "test/lifecycle"}}
    )
    assert r.json()["result"]["status"] == "unregistered"
    r = requests.post(
        CLI, json={"command": "get", "args": {"service_id": "test/lifecycle"}}
    )
    assert "error" in r.json()["result"]


def http_invalid_json():
    r = requests.post(
        CLI, data="not json", headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 400
    data = r.json()
    assert data["error"]["code"] == "invalid_json"


def http_missing_command():
    r = requests.post(CLI, json={})
    assert r.status_code == 400
    data = r.json()
    assert data["error"]["code"] == "invalid_command"


def http_unknown_command():
    r = requests.post(CLI, json={"command": "bogus"})
    assert r.status_code == 404
    data = r.json()
    assert data["error"]["code"] == "command_not_found"


def http_missing_required_arg():
    r = requests.post(CLI, json={"command": "get"})
    assert r.status_code == 400
    data = r.json()
    assert data["error"]["code"] == "missing_required_argument"


def http_register_missing_id():
    r = requests.post(
        CLI, json={"command": "register", "args": {"body": {"url": "http://x"}}}
    )
    assert r.status_code == 200
    data = r.json()
    assert "error" in data["result"]


def http_error_envelope():
    payloads = [
        ("invalid_json", "not json"),
        ("invalid_command", {}),
        ("command_not_found", {"command": "bogus"}),
        ("missing_required_argument", {"command": "get"}),
    ]
    for label, body in payloads:
        if isinstance(body, str):
            r = requests.post(
                CLI, data=body, headers={"Content-Type": "application/json"}
            )
        else:
            r = requests.post(CLI, json=body)
        data = r.json()
        assert data.get("interface") == "cli", f"{label}: missing interface"
        assert data.get("version") == "1.0", f"{label}: missing version"


def http_setstatus():
    svc = {
        "id": "test/statushttp",
        "url": "http://localhost:9996",
        "cli": "/cli/test/statushttp",
        "handles": "http status testing",
        "use_when": "testing",
        "owner": "test",
        "tags": ["test"],
    }
    requests.post(CLI, json={"command": "register", "args": {"body": svc}})

    # set to maintenance
    r = requests.post(
        CLI,
        json={"command": "setstatus", "args": {"service_id": "test/statushttp", "status": "maintenance"}},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["result"]["current"] == "maintenance"
    assert data["result"]["previous"] == "live"

    # surfaced in list
    r = requests.post(CLI, json={"command": "list"})
    entries = {s["id"]: s for s in r.json()["result"]["services"]}
    assert entries["test/statushttp"]["status"] == "maintenance"

    # invalid status
    r = requests.post(
        CLI,
        json={"command": "setstatus", "args": {"service_id": "test/statushttp", "status": "broken"}},
    )
    assert r.status_code == 200
    assert "error" in r.json()["result"]

    requests.post(CLI, json={"command": "unregister", "args": {"service_id": "test/statushttp"}})


def http_update_existing():
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
    requests.post(CLI, json={"command": "register", "args": {"body": svc}})
    svc["handles"] = "updated"
    r = requests.post(CLI, json={"command": "register", "args": {"body": svc}})
    assert r.json()["result"]["status"] == "updated"
    r = requests.post(
        CLI, json={"command": "get", "args": {"service_id": "test/update"}}
    )
    assert r.json()["result"]["service"]["handles"] == "updated"
    requests.post(
        CLI, json={"command": "unregister", "args": {"service_id": "test/update"}}
    )


if __name__ == "__main__":
    print("=" * 60)
    print("Registry Test Suite")
    print("=" * 60)
    print("\n-- registry_core.py (local) --")
    test("core list", core_list)
    test("core get", core_get)
    test("core get not found", core_get_not_found)
    test("core resolve", core_resolve)
    test("core resolve dependencies parsed", core_resolve_dependencies)
    test("core setstatus", core_setstatus)
    test("core register preserves status", core_register_preserves_status)
    test("core resolve includes status", core_resolve_includes_status)
    test("core register + unregister lifecycle", core_register_and_unregister)
    print("\n-- HTTP server (port 7700) --")
    test("GET /health", http_health)
    test("GET /cli/registry discovery", http_discovery)
    test("POST list", http_list)
    test("POST get", http_get)
    test("POST get not found", http_get_not_found)
    test("POST resolve", http_resolve)
    test("POST resolve prerequisites shape", http_resolve_prerequisites_shape)
    test("POST resolve no registry dump", http_resolve_no_registry_dump)
    test("POST register + unregister lifecycle", http_register_and_unregister)
    test("POST setstatus", http_setstatus)
    test("POST register update existing", http_update_existing)
    print("\n-- Error handling --")
    test("invalid JSON", http_invalid_json)
    test("missing command", http_missing_command)
    test("unknown command", http_unknown_command)
    test("missing required arg", http_missing_required_arg)
    test("register without id", http_register_missing_id)
    test("all errors have interface+version", http_error_envelope)
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)
    if errors:
        print("\nFailures:")
        for name, err in errors:
            print(f"  - {name}: {err}")
    sys.exit(1 if failed else 0)
