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


def raw_post(url, data_bytes):
    req = urllib.request.Request(
        url, data=data_bytes, headers={"Content-Type": "application/json"}
    )
    try:
        r = urllib.request.urlopen(req)
        return r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), None


def test_invalid_top_level_array_rejected(tmf620_available):
    code, raw, _ = raw_post(BASE + "/cli/tmf620/catalogmgt", json.dumps([1, 2, 3]).encode())
    body = json.loads(raw)
    assert code == 400
    assert body["error"]["code"] == "invalid_request"


def test_streaming_health_request(tmf620_available):
    code, raw, hdrs = raw_post(
        BASE + "/cli/tmf620/catalogmgt",
        json.dumps({"command": "health", "stream": True}).encode(),
    )
    ct = hdrs.get("Content-Type", "")
    lines = [l for l in raw.decode().strip().split("\n") if l]
    first = json.loads(lines[0])
    last = json.loads(lines[-1])
    assert code == 200
    assert "ndjson" in ct.lower()
    assert first["type"] == "started"
    assert last["type"] in ("done", "result")


def test_extra_fields_are_ignored(tmf620_available):
    code, body = post(
        BASE + "/cli/tmf620/catalogmgt",
        {"command": "health", "args": {}, "stream": False, "extra": True},
    )
    assert code == 200
    assert body["status"] == "ok"


def test_command_whitespace_is_trimmed(tmf620_available):
    code, body = post(BASE + "/cli/tmf620/catalogmgt", {"command": "  health  "})
    assert code == 200
    assert body["status"] == "ok"
    assert body["command"] == "health"


def test_health_with_invalid_args_is_handled(tmf620_available):
    code, body = post(BASE + "/cli/tmf620/catalogmgt", {"command": "health", "args": {"bogus": 123}})
    assert code == 200
    assert body["status"] in {"ok", "error"}


@pytest.mark.parametrize(
    "label,payload",
    [
        ("invalid_json", b"not json"),
        ("invalid_command", json.dumps({}).encode()),
        ("invalid_arguments", json.dumps({"command": "health", "args": [1]}).encode()),
        ("command_not_found", json.dumps({"command": "bogus"}).encode()),
        ("help_target_not_found", json.dumps({"command": "help", "args": {"command": "bogus"}}).encode()),
        ("missing_required_argument", json.dumps({"command": "catalog get"}).encode()),
    ],
)
def test_error_envelope_has_cli_version(tmf620_available, label, payload):
    code, raw, _ = raw_post(BASE + "/cli/tmf620/catalogmgt", payload)
    body = json.loads(raw)
    assert code in {400, 404}, label
    assert body.get("interface") == "cli", label
    assert body.get("version") == "1.0", label


def test_help_root_is_ok(tmf620_available):
    code, body = post(BASE + "/cli/tmf620/catalogmgt", {"command": "help"})
    assert code == 200
    assert body["status"] == "ok"


def test_health_command_shape(tmf620_available):
    code, body = post(BASE + "/cli/tmf620/catalogmgt", {"command": "health"})
    assert code == 200
    assert body["status"] == "ok"
    assert body["interface"] == "cli"
    assert body["version"] == "1.0"
    assert body["command"] == "health"
    assert "result" in body


def test_command_help_shape(tmf620_available):
    code, body = post(
        BASE + "/cli/tmf620/catalogmgt",
        {"command": "help", "args": {"command": "catalog list"}},
    )
    assert code == 200
    assert "status" in body
    assert "interface" in body
    assert "version" in body
    assert "command" in body
    assert "summary" in body
    assert "arguments" in body
    assert "examples" in body
    assert "result" not in body


def test_catalog_group_command_response_is_valid(tmf620_available):
    code, body = post(BASE + "/cli/tmf620/catalogmgt", {"command": "catalog"})
    assert code in (200, 400)
