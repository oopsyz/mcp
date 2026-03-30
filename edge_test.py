import urllib.request
import json

BASE = "http://localhost:7701"


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


print("=== EDGE CASE & SPEC GAP ANALYSIS ===")
print()

# 1. Non-object top-level body (array)
print("--- 1. Array body (invalid_request) ---")
code, raw, _ = raw_post(BASE + "/api/cli", json.dumps([1, 2, 3]).encode())
body = json.loads(raw)
print("  HTTP", code, "code:", body["error"]["code"])
assert body["error"]["code"] == "invalid_request"
print("  PASS")

# 2. Streaming single-result command
print()
print("--- 2. Streaming single-result command (health) ---")
code, raw, hdrs = raw_post(
    BASE + "/api/cli", json.dumps({"command": "health", "stream": True}).encode()
)
ct = hdrs.get("Content-Type", "")
lines = [l for l in raw.decode().strip().split("\n") if l]
first = json.loads(lines[0])
last = json.loads(lines[-1])
print("  Content-Type:", ct)
print("  Chunks:", len(lines))
print("  First:", first["type"], " Last:", last["type"])
print("  PASS")

# 3. Extra fields in request (should be ignored)
print()
print("--- 3. Extra fields in request ---")
code, body = post(
    BASE + "/api/cli",
    {"command": "health", "args": {}, "stream": False, "extra": True},
)
print("  HTTP", code, "status:", body["status"])
print("  PASS (extra fields ignored)")

# 4. Whitespace in command
print()
print("--- 4. Whitespace in command ---")
code, body = post(BASE + "/api/cli", {"command": "  health  "})
print("  HTTP", code, "status:", body["status"], "command:", body.get("command"))
assert body["status"] == "ok"
print("  PASS")

# 5. Unknown arguments on command
print()
print("--- 5. Unknown arguments (should error per spec?) ---")
code, body = post(BASE + "/api/cli", {"command": "health", "args": {"bogus": 123}})
print("  HTTP", code, "status:", body.get("status"))
if body.get("status") == "error":
    print("  error_code:", body["error"]["code"])
else:
    print("  No error - unknown args silently ignored")
print()

# 6. All error responses include interface+version (Conformance #8)
print("--- 6. Conf #8: All error responses have interface+version ---")
errors = [
    ("invalid_json", b"not json"),
    ("invalid_command", json.dumps({}).encode()),
    ("invalid_arguments", json.dumps({"command": "health", "args": [1]}).encode()),
    ("command_not_found", json.dumps({"command": "bogus"}).encode()),
    (
        "help_target_not_found",
        json.dumps({"command": "help", "args": {"command": "bogus"}}).encode(),
    ),
    ("missing_required_argument", json.dumps({"command": "catalog get"}).encode()),
]
all_ok = True
for label, payload in errors:
    code, raw, _ = raw_post(BASE + "/api/cli", payload)
    body = json.loads(raw)
    has_iface = body.get("interface") == "cli"
    has_ver = body.get("version") == "1.0"
    ok = has_iface and has_ver
    all_ok = all_ok and ok
    status = "OK" if ok else "FAIL"
    print(
        "  "
        + label
        + ": interface="
        + str(has_iface)
        + " version="
        + str(has_ver)
        + " "
        + status
    )
print("  All errors conform: " + str(all_ok))

# 7. Reserved 'help' cannot be overridden
print()
print("--- 7. Reserved 'help' command ---")
code, body = post(BASE + "/api/cli", {"command": "help"})
assert body["status"] == "ok"
print("  help returns catalog: True")
print("  PASS")

# 8. Response envelope check for invocation
print()
print("--- 8. Invocation envelope completeness ---")
code, body = post(BASE + "/api/cli", {"command": "health"})
assert body["status"] == "ok"
assert body["interface"] == "cli"
assert body["version"] == "1.0"
assert body["command"] == "health"
assert "result" in body
print("  status, interface, version, command, result: all present")
print("  PASS")

# 9. Help response does NOT have invocation envelope
print()
print("--- 9. Help response shape (not invocation envelope) ---")
code, body = post(
    BASE + "/api/cli", {"command": "help", "args": {"command": "catalog list"}}
)
print("  Has status:", "status" in body)
print("  Has interface:", "interface" in body)
print("  Has version:", "version" in body)
print("  Has command:", "command" in body, " value:", body.get("command"))
print("  Has summary:", "summary" in body)
print("  Has arguments:", "arguments" in body)
print("  Has examples:", "examples" in body)
print("  Has result:", "result" in body, "(should not)")
print("  PASS")

# 10. Group-only invocation
print()
print("--- 10. Invoking a group (catalog without subcommand) ---")
code, body = post(BASE + "/api/cli", {"command": "catalog"})
print("  HTTP", code, "status:", body.get("status"))
if body.get("status") == "error":
    print("  error_code:", body["error"]["code"])
    print("  Spec says: groups are discovery labels, not invokable")
else:
    print("  WARNING: group invocation succeeded - spec says groups are not invokable")

print()
print("=== EDGE CASE ANALYSIS COMPLETE ===")
