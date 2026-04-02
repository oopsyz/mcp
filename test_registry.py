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
    assert "registry_content" in result
    assert "services" in result
    assert "instruction" in result


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
    assert len(data["commands"]) == 5
    names = [c["name"] for c in data["commands"]]
    for expected in ["list", "get", "resolve", "register", "unregister"]:
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
            "args": {"query": "I need to manage product orders"},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    result = data["result"]
    assert "query" in result
    assert "registry_content" in result
    assert "services" in result
    assert "instruction" in result


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
    test("core register + unregister lifecycle", core_register_and_unregister)
    print("\n-- HTTP server (port 7700) --")
    test("GET /health", http_health)
    test("GET /cli/registry discovery", http_discovery)
    test("POST list", http_list)
    test("POST get", http_get)
    test("POST get not found", http_get_not_found)
    test("POST resolve", http_resolve)
    test("POST register + unregister lifecycle", http_register_and_unregister)
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
