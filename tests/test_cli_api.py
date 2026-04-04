import json

import pytest
import requests


CLI_URL = "http://localhost:7701/cli/tmf620/catalogmgt"
HEALTH_URL = "http://localhost:7701/health"


def _service_up() -> bool:
    try:
        return requests.get(HEALTH_URL, timeout=3).status_code == 200
    except requests.RequestException:
        return False


@pytest.fixture(scope="session")
def tmf620_available():
    if not _service_up():
        pytest.skip("TMF620 stack is not running")


def _get(url):
    r = requests.get(url, timeout=30)
    assert r.status_code == 200, f"GET {url} failed: {r.text}"
    return r.json()


def _post(url, payload):
    r = requests.post(url, json=payload, timeout=30)
    return r.status_code, r.json()


def _post_raw(url, payload, headers=None):
    r = requests.post(url, data=payload, headers=headers, timeout=30)
    return r.status_code, r.text, r.headers


def test_cli_api_health_endpoint(tmf620_available):
    data = _get(HEALTH_URL)
    assert data["status"] == "healthy"
    assert data["api_connection"] == "successful"


def test_cli_api_discovery(tmf620_available):
    data = _get(CLI_URL)
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


def test_cli_api_help_routes(tmf620_available):
    data = _post(CLI_URL, {"command": "help"})[1]
    assert data["status"] == "ok"
    assert data["interface"] == "cli"
    assert len(data["commands"]) > 0

    data = _post(CLI_URL, {"command": "help", "args": {"command": "catalog list"}})[1]
    assert data["status"] == "ok"
    assert data["command"] == "catalog list"
    assert "arguments" in data
    assert len(data["examples"]) > 0

    data = _post(CLI_URL, {"command": "help", "args": {"command": "catalog"}})[1]
    assert data["status"] == "ok"
    assert data["kind"] == "group"
    assert len(data["subcommands"]) > 0

    status, data = _post(
        CLI_URL, {"command": "help", "args": {"command": "nonexistent"}}
    )
    assert status == 404
    assert data["status"] == "error"
    assert data["error"]["code"] == "help_target_not_found"


def test_cli_api_health_and_config_commands(tmf620_available):
    data = _post(CLI_URL, {"command": "health"})[1]
    assert data["status"] == "ok"
    assert data["result"]["status"] == "healthy"

    data = _post(CLI_URL, {"command": "config"})[1]
    assert data["status"] == "ok"
    assert "tmf620_api" in data["result"]


def test_cli_api_catalog_commands(tmf620_available):
    data = _post(CLI_URL, {"command": "catalog list"})[1]
    assert data["status"] == "ok"
    assert isinstance(data["result"], list)
    assert len(data["result"]) > 0
    assert data["result"][0]["name"] is not None

    data = _post(CLI_URL, {"command": "catalog list", "args": {"limit": 1}})[1]
    assert data["status"] == "ok"
    assert len(data["result"]) <= 1

    data = _post(
        CLI_URL, {"command": "catalog list", "args": {"lifecycle_status": "Active"}}
    )[1]
    assert data["status"] == "ok"
    for item in data["result"]:
        assert item.get("lifecycleStatus") == "Active"

    data = _post(
        CLI_URL, {"command": "catalog get", "args": {"catalog_id": "cat-001"}}
    )[1]
    assert data["status"] == "ok"
    assert data["result"]["id"] == "cat-001"
    assert data["result"]["name"] == "Enterprise Services Catalog"

    status, data = _post(
        CLI_URL, {"command": "catalog get", "args": {"catalog_id": "nonexistent"}}
    )
    assert status == 200
    assert data["status"] == "error"
    assert data["error"]["code"] == "tool_invocation_failed"


def test_cli_api_offering_commands(tmf620_available):
    data = _post(CLI_URL, {"command": "offering list"})[1]
    assert data["status"] == "ok"
    assert isinstance(data["result"], list)
    assert len(data["result"]) > 0

    data = _post(
        CLI_URL, {"command": "offering list", "args": {"catalog_id": "cat-001"}}
    )[1]
    assert data["status"] == "ok"
    for item in data["result"]:
        assert item.get("catalogId") == "cat-001"

    data = _post(
        CLI_URL, {"command": "offering get", "args": {"offering_id": "po-001"}}
    )[1]
    assert data["status"] == "ok"
    assert data["result"]["id"] == "po-001"


def test_cli_api_category_list(tmf620_available):
    data = _post(CLI_URL, {"command": "category list"})[1]
    assert data["status"] == "ok"
    assert isinstance(data["result"], list)
    assert len(data["result"]) >= 2

    data = _post(CLI_URL, {"command": "category list", "args": {"limit": 1}})[1]
    assert data["status"] == "ok"
    assert len(data["result"]) <= 1


def test_cli_api_category_get(tmf620_available):
    data = _post(
        CLI_URL,
        {"command": "category get", "args": {"category_id": "category-internet"}},
    )[1]
    assert data["status"] == "ok"
    assert data["result"]["id"] == "category-internet"


def test_cli_api_specification_commands(tmf620_available):
    data = _post(CLI_URL, {"command": "specification list"})[1]
    assert data["status"] == "ok"
    assert isinstance(data["result"], list)
    assert len(data["result"]) >= 2

    data = _post(
        CLI_URL,
        {"command": "specification get", "args": {"specification_id": "ps-001"}},
    )[1]
    assert data["status"] == "ok"
    assert data["result"]["id"] == "ps-001"


def test_cli_api_price_commands(tmf620_available):
    data = _post(CLI_URL, {"command": "price list"})[1]
    assert data["status"] == "ok"
    assert isinstance(data["result"], list)
    assert len(data["result"]) >= 1

    data = _post(CLI_URL, {"command": "price get", "args": {"price_id": "pop-001"}})[1]
    assert data["status"] == "ok"
    assert data["result"]["id"] == "pop-001"


def test_cli_api_import_export_commands(tmf620_available):
    data = _post(CLI_URL, {"command": "import-job list"})[1]
    assert data["status"] == "ok"
    assert isinstance(data["result"], list)
    assert len(data["result"]) >= 1

    data = _post(
        CLI_URL, {"command": "import-job get", "args": {"import_job_id": "import-001"}}
    )[1]
    assert data["status"] == "ok"
    assert data["result"]["id"] == "import-001"

    data = _post(CLI_URL, {"command": "export-job list"})[1]
    assert data["status"] == "ok"
    assert isinstance(data["result"], list)
    assert len(data["result"]) >= 1

    data = _post(
        CLI_URL, {"command": "export-job get", "args": {"export_job_id": "export-001"}}
    )[1]
    assert data["status"] == "ok"
    assert data["result"]["id"] == "export-001"


def test_cli_api_catalog_create_delete(tmf620_available):
    create = _post(
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
    )[1]
    assert create["status"] == "ok"
    assert create["result"]["name"] == "Test Catalog"
    catalog_id = create["result"]["id"]

    try:
        get = _post(CLI_URL, {"command": "catalog get", "args": {"catalog_id": catalog_id}})[1]
        assert get["status"] == "ok"
        assert get["result"]["name"] == "Test Catalog"

        delete = _post(
            CLI_URL, {"command": "catalog delete", "args": {"catalog_id": catalog_id}}
        )[1]
        assert delete["status"] == "ok"

        get2 = _post(
            CLI_URL, {"command": "catalog get", "args": {"catalog_id": catalog_id}}
        )[1]
        assert get2["status"] == "error"
    finally:
        _post(CLI_URL, {"command": "catalog delete", "args": {"catalog_id": catalog_id}})


def test_cli_api_hub_create_delete(tmf620_available):
    create = _post(
        CLI_URL,
        {
            "command": "hub create",
            "args": {
                "body": {
                    "callback": "http://localhost:9999/test-hook",
                }
            },
        },
    )[1]
    assert create["status"] == "ok"
    hub_id = create["result"]["id"]
    delete = _post(CLI_URL, {"command": "hub delete", "args": {"hub_id": hub_id}})[1]
    assert delete["status"] == "ok"


def test_cli_api_streaming_response(tmf620_available):
    r = requests.post(
        CLI_URL,
        json={"command": "health", "stream": True},
        timeout=30,
    )
    assert r.status_code == 200
    lines = [line for line in r.text.strip().splitlines() if line.strip()]
    assert len(lines) >= 2, f"Expected >=2 NDJSON lines, got {len(lines)}"
    first = json.loads(lines[0])
    assert first["type"] == "started"
    last = json.loads(lines[-1])
    assert last["type"] in ("result", "done")


@pytest.mark.parametrize(
    "payload, expected_code, expected_http_status",
    [
        (b"not json", "invalid_json", 400),
        (json.dumps({}).encode(), "invalid_command", 400),
        (json.dumps({"command": "bogus"}).encode(), "command_not_found", 404),
        (json.dumps({"command": "catalog get"}).encode(), "missing_required_argument", 400),
        (json.dumps({"command": "health", "args": [1, 2]}).encode(), "invalid_arguments", 400),
        (json.dumps({"command": "health", "stream": "yes"}).encode(), "invalid_request", 400),
    ],
)
def test_cli_api_invalid_request_cases(tmf620_available, payload, expected_code, expected_http_status):
    code, raw, _ = _post_raw(CLI_URL, payload, headers={"Content-Type": "application/json"})
    body = json.loads(raw)
    assert code == expected_http_status
    assert body["error"]["code"] == expected_code


def test_cli_api_invocation_response_shape(tmf620_available):
    code, body = _post(CLI_URL, {"command": "health"})
    assert code == 200
    assert body["status"] == "ok"
    assert body["interface"] == "cli"
    assert body["version"] == "1.0"
    assert "command" in body
    assert "result" in body


def test_cli_api_error_response_shape(tmf620_available):
    code, body = _post(CLI_URL, {"command": "catalog get"})
    assert code == 400
    assert body["status"] == "error"
    assert body["interface"] == "cli"
    assert body["version"] == "1.0"
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]
    assert body["error"]["code"].replace("_", "").isalpha()


def test_cli_api_help_for_help(tmf620_available):
    code, body = _post(
        CLI_URL, {"command": "help", "args": {"command": "help"}}
    )
    assert code == 200
    assert body["status"] == "ok"
