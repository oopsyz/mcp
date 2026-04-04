from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest


BASE = "http://localhost:7701"


def _service_up() -> bool:
    try:
        return urllib.request.urlopen(BASE + "/health", timeout=3).status == 200
    except Exception:
        return False


@pytest.fixture(scope="session")
def tmf620_available():
    if not _service_up():
        pytest.skip("TMF620 stack is not running")


def post(url, data):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        r = urllib.request.urlopen(req)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def get(url):
    r = urllib.request.urlopen(url)
    return r.status, json.loads(r.read())


def raw_post(url, data_bytes):
    req = urllib.request.Request(
        url, data=data_bytes, headers={"Content-Type": "application/json"}
    )
    try:
        r = urllib.request.urlopen(req)
        return r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), None


def test_cli_root_discovery(tmf620_available):

    code, body = get(BASE + "/cli/tmf620/catalogmgt")
    assert code == 200
    assert body["status"] == "ok"
    assert body["interface"] == "cli"
    assert body["version"] == "1.0"
    assert body["service"] == "tmf620"
    assert body["namespace"] == "tmf620/catalogmgt"
    assert body["canonical_endpoint"] == "/cli/tmf620/catalogmgt"
    assert "commands" in body
    assert body["total"] == len(body["commands"])
    for cmd in body["commands"]:
        assert "name" in cmd and "kind" in cmd and "summary" in cmd
        assert cmd["kind"] in ("command", "group")
        assert "arguments" not in cmd


def test_cli_help_root(tmf620_available):

    code, body = post(BASE + "/cli/tmf620/catalogmgt", {"command": "help"})
    assert code == 200
    assert body["status"] == "ok" and body["interface"] == "cli"
    assert body["total"] == len(body["commands"])


def test_cli_group_help(tmf620_available):

    code, body = post(
        BASE + "/cli/tmf620/catalogmgt", {"command": "help", "args": {"command": "catalog"}}
    )
    assert code == 200
    assert body["status"] == "ok"
    assert body["kind"] == "group"
    assert "subcommands" in body
    for sub in body["subcommands"]:
        assert "name" in sub and "kind" in sub and "summary" in sub
        assert "arguments" not in sub


def test_cli_command_help(tmf620_available):

    code, body = post(
        BASE + "/cli/tmf620/catalogmgt",
        {"command": "help", "args": {"command": "catalog list"}},
    )
    assert code == 200
    assert body["status"] == "ok"
    assert body["command"] == "catalog list"
    assert "arguments" in body
    for arg in body["arguments"]:
        assert "name" in arg and "required" in arg and "default" in arg


def test_cli_help_unknown_target(tmf620_available):

    code, body = post(
        BASE + "/cli/tmf620/catalogmgt", {"command": "help", "args": {"command": "bogus"}}
    )
    assert code == 404
    assert body["status"] == "error"
    assert body["error"]["code"] == "help_target_not_found"


@pytest.mark.parametrize(
    "payload, expected_code, expected_http_status",
    [
        (b"not json", "invalid_json", 400),
        (json.dumps({}).encode(), "invalid_command", 400),
        (json.dumps({"command": "bogus_command"}).encode(), "command_not_found", 404),
        (json.dumps({"command": "catalog get"}).encode(), "missing_required_argument", 400),
        (json.dumps({"command": "health", "args": [1, 2]}).encode(), "invalid_arguments", 400),
        (json.dumps({"command": "health", "stream": "yes"}).encode(), "invalid_request", 400),
    ],
)
def test_cli_invalid_request_cases(tmf620_available, payload, expected_code, expected_http_status):

    code, raw, _ = raw_post(BASE + "/cli/tmf620/catalogmgt", payload)
    body = json.loads(raw)
    assert code == expected_http_status
    assert body["error"]["code"] == expected_code


def test_cli_streaming_response(tmf620_available):

    code, raw, headers = raw_post(
        BASE + "/cli/tmf620/catalogmgt",
        json.dumps({"command": "catalog list", "stream": True}).encode(),
    )
    ct = headers.get("Content-Type", "") if headers else ""
    text = raw.decode()
    lines = [l for l in text.strip().split("\n") if l]
    first = json.loads(lines[0])
    last = json.loads(lines[-1])
    assert code == 200
    assert "ndjson" in ct.lower()
    assert first["type"] == "started"
    assert first["interface"] == "cli"
    assert last["type"] in ("done", "result")


def test_cli_invocation_response_shape(tmf620_available):

    code, body = post(BASE + "/cli/tmf620/catalogmgt", {"command": "health"})
    assert code == 200
    assert body["status"] == "ok"
    assert body["interface"] == "cli"
    assert body["version"] == "1.0"
    assert "command" in body
    assert "result" in body


def test_cli_error_response_shape(tmf620_available):

    code, body = post(BASE + "/cli/tmf620/catalogmgt", {"command": "catalog get"})
    assert code == 400
    assert body["status"] == "error"
    assert body["interface"] == "cli"
    assert body["version"] == "1.0"
    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]
    assert body["error"]["code"].replace("_", "").isalpha()


def test_cli_help_for_help(tmf620_available):

    code, body = post(
        BASE + "/cli/tmf620/catalogmgt", {"command": "help", "args": {"command": "help"}}
    )
    assert code == 200
    assert body["status"] == "ok"
