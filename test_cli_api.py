import json
import subprocess
import sys

CLI_URL = "http://localhost:7701/cli/tmf620/catalogmgt"
HEALTH_URL = "http://localhost:7701/health"
passed = 0
failed = 0
errors = []


def _curl_get(url):
    r = subprocess.run(
        ["curl", "-sf", url],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, f"curl GET {url} failed: {r.stderr}"
    return json.loads(r.stdout)


def _curl_post(url, payload):
    r = subprocess.run(
        [
            "curl",
            "-sf",
            "-X",
            "POST",
            url,
            "-H",
            "Content-Type: application/json",
            "-d",
            json.dumps(payload),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, f"curl POST {url} failed: {r.stderr}"
    return json.loads(r.stdout)


def _curl_post_raw(url, payload):
    r = subprocess.run(
        [
            "curl",
            "-s",
            "-X",
            "POST",
            url,
            "-H",
            "Content-Type: application/json",
            "-d",
            json.dumps(payload),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return r.returncode, json.loads(r.stdout) if r.stdout.strip() else {}


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


def health_get():
    data = _curl_get(HEALTH_URL)
    assert data["status"] == "healthy", f"Expected healthy, got {data}"
    assert data["api_connection"] == "successful", f"API connection failed: {data}"


def cli_catalog_get():
    data = _curl_get(CLI_URL)
    assert data["status"] == "ok"
    assert data["interface"] == "cli"
    assert data["version"] == "1.0"
    assert data["service"] == "tmf620"
    assert data["namespace"] == "tmf620/catalogmgt"
    assert data["canonical_endpoint"] == "/cli/tmf620/catalogmgt"
    assert len(data["commands"]) > 0
    names = [c["name"] for c in data["commands"]]
    for expected in ["health", "config", "catalog", "offering", "category", "hub"]:
        assert expected in names, f"Missing command: {expected}"


def help_via_post_no_args():
    data = _curl_post(CLI_URL, {"command": "help"})
    assert data["status"] == "ok"
    assert data["interface"] == "cli"
    assert len(data["commands"]) > 0


def help_specific_command():
    data = _curl_post(CLI_URL, {"command": "help", "args": {"command": "catalog list"}})
    assert data["status"] == "ok"
    assert data["command"] == "catalog list"
    assert "arguments" in data
    assert len(data["examples"]) > 0


def help_group_command():
    data = _curl_post(CLI_URL, {"command": "help", "args": {"command": "catalog"}})
    assert data["status"] == "ok"
    assert data["kind"] == "group"
    assert len(data["subcommands"]) > 0


def help_unknown_command():
    rc, data = _curl_post_raw(
        CLI_URL, {"command": "help", "args": {"command": "nonexistent"}}
    )
    assert data["status"] == "error"
    assert data["error"]["code"] == "help_target_not_found"


def health_command():
    data = _curl_post(CLI_URL, {"command": "health"})
    assert data["status"] == "ok"
    assert data["result"]["status"] == "healthy"


def config_command():
    data = _curl_post(CLI_URL, {"command": "config"})
    assert data["status"] == "ok"
    assert "tmf620_api" in data["result"]


def catalog_list():
    data = _curl_post(CLI_URL, {"command": "catalog list"})
    assert data["status"] == "ok"
    assert isinstance(data["result"], list)
    assert len(data["result"]) > 0
    assert data["result"][0]["name"] is not None


def catalog_list_with_limit():
    data = _curl_post(CLI_URL, {"command": "catalog list", "args": {"limit": 1}})
    assert data["status"] == "ok"
    assert len(data["result"]) <= 1


def catalog_list_with_lifecycle():
    data = _curl_post(
        CLI_URL, {"command": "catalog list", "args": {"lifecycle_status": "Active"}}
    )
    assert data["status"] == "ok"
    for item in data["result"]:
        assert item.get("lifecycleStatus") == "Active"


def catalog_get():
    data = _curl_post(
        CLI_URL, {"command": "catalog get", "args": {"catalog_id": "cat-001"}}
    )
    assert data["status"] == "ok"
    assert data["result"]["id"] == "cat-001"
    assert data["result"]["name"] == "Enterprise Services Catalog"


def catalog_get_not_found():
    rc, data = _curl_post_raw(
        CLI_URL, {"command": "catalog get", "args": {"catalog_id": "nonexistent"}}
    )
    assert data["status"] == "error"
    assert data["error"]["code"] == "tool_invocation_failed"


def offering_list():
    data = _curl_post(CLI_URL, {"command": "offering list"})
    assert data["status"] == "ok"
    assert isinstance(data["result"], list)
    assert len(data["result"]) > 0


def offering_list_with_catalog_filter():
    data = _curl_post(
        CLI_URL, {"command": "offering list", "args": {"catalog_id": "cat-001"}}
    )
    assert data["status"] == "ok"
    for item in data["result"]:
        assert item.get("catalogId") == "cat-001"


def offering_get():
    data = _curl_post(
        CLI_URL, {"command": "offering get", "args": {"offering_id": "po-001"}}
    )
    assert data["status"] == "ok"
    assert data["result"]["id"] == "po-001"


def category_list():
    data = _curl_post(CLI_URL, {"command": "category list"})
    assert data["status"] == "ok"
    assert isinstance(data["result"], list)
    assert len(data["result"]) >= 2


def category_get():
    data = _curl_post(
        CLI_URL,
        {"command": "category get", "args": {"category_id": "category-internet"}},
    )
    assert data["status"] == "ok"
    assert data["result"]["id"] == "category-internet"


def specification_list():
    data = _curl_post(CLI_URL, {"command": "specification list"})
    assert data["status"] == "ok"
    assert isinstance(data["result"], list)
    assert len(data["result"]) >= 2


def specification_get():
    data = _curl_post(
        CLI_URL,
        {"command": "specification get", "args": {"specification_id": "ps-001"}},
    )
    assert data["status"] == "ok"
    assert data["result"]["id"] == "ps-001"


def price_list():
    data = _curl_post(CLI_URL, {"command": "price list"})
    assert data["status"] == "ok"
    assert isinstance(data["result"], list)
    assert len(data["result"]) >= 1


def price_get():
    data = _curl_post(
        CLI_URL, {"command": "price get", "args": {"price_id": "pop-001"}}
    )
    assert data["status"] == "ok"
    assert data["result"]["id"] == "pop-001"


def import_job_list():
    data = _curl_post(CLI_URL, {"command": "import-job list"})
    assert data["status"] == "ok"
    assert isinstance(data["result"], list)
    assert len(data["result"]) >= 1


def import_job_get():
    data = _curl_post(
        CLI_URL, {"command": "import-job get", "args": {"import_job_id": "import-001"}}
    )
    assert data["status"] == "ok"
    assert data["result"]["id"] == "import-001"


def export_job_list():
    data = _curl_post(CLI_URL, {"command": "export-job list"})
    assert data["status"] == "ok"
    assert isinstance(data["result"], list)
    assert len(data["result"]) >= 1


def export_job_get():
    data = _curl_post(
        CLI_URL, {"command": "export-job get", "args": {"export_job_id": "export-001"}}
    )
    assert data["status"] == "ok"
    assert data["result"]["id"] == "export-001"


def empty_command():
    rc, data = _curl_post_raw(CLI_URL, {"command": ""})
    assert data["status"] == "error"
    assert data["error"]["code"] == "invalid_command"


def missing_command_key():
    rc, data = _curl_post_raw(CLI_URL, {})
    assert data["status"] == "error"
    assert data["error"]["code"] == "invalid_command"


def unknown_command():
    rc, data = _curl_post_raw(CLI_URL, {"command": "nonexistent"})
    assert data["status"] == "error"
    assert data["error"]["code"] == "command_not_found"


def missing_required_arg():
    rc, data = _curl_post_raw(CLI_URL, {"command": "catalog get"})
    assert data["status"] == "error"
    assert data["error"]["code"] == "missing_required_argument"


def invalid_json_body():
    r = subprocess.run(
        [
            "curl",
            "-s",
            "-X",
            "POST",
            CLI_URL,
            "-H",
            "Content-Type: application/json",
            "-d",
            "not json",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    data = json.loads(r.stdout)
    assert data["status"] == "error"
    assert data["error"]["code"] == "invalid_json"


def args_not_object():
    rc, data = _curl_post_raw(CLI_URL, {"command": "health", "args": "invalid"})
    assert data["status"] == "error"
    assert data["error"]["code"] == "invalid_arguments"


def unknown_argument():
    rc, data = _curl_post_raw(CLI_URL, {"command": "health", "args": {"bogus": 1}})
    assert data["status"] == "error"
    assert data["error"]["code"] == "invalid_argument"


def catalog_create_and_delete():
    create = _curl_post(
        CLI_URL,
        {
            "command": "catalog create",
            "args": {
                "body": {
                    "name": "Test Catalog",
                    "description": "Created by test suite",
                    "@type": "ProductCatalog",
                }
            },
        },
    )
    assert create["status"] == "ok"
    assert create["result"]["name"] == "Test Catalog"
    catalog_id = create["result"]["id"]

    get = _curl_post(
        CLI_URL, {"command": "catalog get", "args": {"catalog_id": catalog_id}}
    )
    assert get["status"] == "ok"
    assert get["result"]["name"] == "Test Catalog"

    delete = _curl_post(
        CLI_URL, {"command": "catalog delete", "args": {"catalog_id": catalog_id}}
    )
    assert delete["status"] == "ok"

    rc, get2 = _curl_post_raw(
        CLI_URL, {"command": "catalog get", "args": {"catalog_id": catalog_id}}
    )
    assert get2["status"] == "error"


def hub_create_and_delete():
    create = _curl_post(
        CLI_URL,
        {
            "command": "hub create",
            "args": {
                "body": {
                    "callback": "http://localhost:9999/test-hook",
                }
            },
        },
    )
    assert create["status"] == "ok"
    hub_id = create["result"]["id"]

    delete = _curl_post(CLI_URL, {"command": "hub delete", "args": {"hub_id": hub_id}})
    assert delete["status"] == "ok"


def streaming_response():
    r = subprocess.run(
        [
            "curl",
            "-s",
            "-X",
            "POST",
            CLI_URL,
            "-H",
            "Content-Type: application/json",
            "-d",
            json.dumps({"command": "health", "stream": True}),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    lines = [line for line in r.stdout.strip().splitlines() if line.strip()]
    assert len(lines) >= 2, f"Expected >=2 NDJSON lines, got {len(lines)}"
    first = json.loads(lines[0])
    assert first["type"] == "started"
    last = json.loads(lines[-1])
    assert last["type"] in ("result", "done")


def mcp_route_valid_call():
    data = _curl_post("http://localhost:7701/commands/health", {"args": {}})
    assert isinstance(data, dict)
    assert data["status"] == "healthy"


def mcp_route_unknown_arg():
    rc, data = _curl_post_raw(
        "http://localhost:7701/commands/health", {"args": {"bogus": 1}}
    )
    assert data["status"] == "error"
    assert data["error"]["code"] == "invalid_argument"


def mcp_route_missing_required_arg():
    rc, data = _curl_post_raw(
        "http://localhost:7701/commands/catalog/get", {"args": {}}
    )
    assert data["status"] == "error"
    assert data["error"]["code"] == "missing_required_argument"


def mcp_route_list_with_limit():
    data = _curl_post(
        "http://localhost:7701/commands/catalog/list", {"args": {"limit": 1}}
    )
    assert isinstance(data, list)
    assert len(data) <= 1


def mcp_route_get_by_id():
    data = _curl_post(
        "http://localhost:7701/commands/catalog/get",
        {"args": {"catalog_id": "cat-001"}},
    )
    assert data["id"] == "cat-001"


def mcp_route_offering_list():
    data = _curl_post("http://localhost:7701/commands/offering/list", {"args": {}})
    assert isinstance(data, list)
    assert len(data) >= 1


def mcp_route_create_and_delete():
    data = _curl_post(
        "http://localhost:7701/commands/category/create",
        {
            "args": {
                "body": {
                    "name": "MCP Test Category",
                    "@type": "Category",
                }
            }
        },
    )
    assert data["name"] == "MCP Test Category"
    cat_id = data["id"]

    get = _curl_post(
        f"http://localhost:7701/commands/category/get",
        {"args": {"category_id": cat_id}},
    )
    assert get["name"] == "MCP Test Category"

    _curl_post(
        f"http://localhost:7701/commands/category/delete",
        {"args": {"category_id": cat_id}},
    )


if __name__ == "__main__":
    print("=" * 60)
    print("CLI API Test Suite")
    print("=" * 60)

    print("\n-- Health & Discovery --")
    test("GET /health returns healthy", health_get)
    test("GET /cli/tmf620/catalogmgt returns command catalog", cli_catalog_get)
    test("POST help (no args) returns catalog", help_via_post_no_args)
    test("POST help for specific command", help_specific_command)
    test("POST help for group command", help_group_command)
    test("POST help for unknown command returns error", help_unknown_command)

    print("\n-- Health & Config Commands --")
    test("health command returns healthy", health_command)
    test("config command returns config", config_command)

    print("\n-- Catalog CRUD --")
    test("catalog list returns catalogs", catalog_list)
    test("catalog list with limit", catalog_list_with_limit)
    test("catalog list with lifecycle filter", catalog_list_with_lifecycle)
    test("catalog get by id", catalog_get)
    test("catalog get nonexistent returns error", catalog_get_not_found)
    test("catalog create and delete", catalog_create_and_delete)

    print("\n-- Offering Commands --")
    test("offering list returns offerings", offering_list)
    test("offering list with catalog filter", offering_list_with_catalog_filter)
    test("offering get by id", offering_get)

    print("\n-- Category Commands --")
    test("category list returns categories", category_list)
    test("category get by id", category_get)

    print("\n-- Specification Commands --")
    test("specification list returns specs", specification_list)
    test("specification get by id", specification_get)

    print("\n-- Price Commands --")
    test("price list returns prices", price_list)
    test("price get by id", price_get)

    print("\n-- Import/Export Job Commands --")
    test("import-job list returns jobs", import_job_list)
    test("import-job get by id", import_job_get)
    test("export-job list returns jobs", export_job_list)
    test("export-job get by id", export_job_get)

    print("\n-- Hub Commands --")
    test("hub create and delete", hub_create_and_delete)

    print("\n-- Streaming --")
    test("streaming response returns NDJSON", streaming_response)

    print("\n-- MCP Routes --")
    test("MCP health route returns healthy", mcp_route_valid_call)
    test("MCP health route rejects unknown arg", mcp_route_unknown_arg)
    test(
        "MCP catalog get route rejects missing required arg",
        mcp_route_missing_required_arg,
    )
    test("MCP catalog list route supports limit", mcp_route_list_with_limit)
    test("MCP catalog get route returns by id", mcp_route_get_by_id)
    test("MCP offering list route returns offerings", mcp_route_offering_list)
    test("MCP category create/get/delete lifecycle", mcp_route_create_and_delete)

    print("\n-- Error Handling --")
    test("empty command returns error", empty_command)
    test("missing command key returns error", missing_command_key)
    test("unknown command returns error", unknown_command)
    test("missing required arg returns error", missing_required_arg)
    test("invalid JSON body returns error", invalid_json_body)
    test("args not object returns error", args_not_object)
    test("unknown argument returns error", unknown_argument)

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    if errors:
        print("\nFailures:")
        for name, err in errors:
            print(f"  - {name}: {err}")

    sys.exit(1 if failed else 0)


