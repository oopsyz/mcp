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


print("=== SPEC.md CONFORMANCE TEST SUITE ===")
print()

# 1. GET /api/cli - root catalog (Conformance #1)
print("--- 1. GET /api/cli (root catalog) [Conf #1,#4] ---")
code, body = get(BASE + "/api/cli")
print("  HTTP", code)
print(
    "  status:",
    body.get("status"),
    " interface:",
    body.get("interface"),
    " version:",
    body.get("version"),
)
print("  service:", body.get("service"))
print("  commands:", body.get("total"))
assert body["status"] == "ok"
assert body["interface"] == "cli"
assert body["version"] == "1.0"
assert "commands" in body
assert body["total"] == len(body["commands"])
for cmd in body["commands"]:
    assert "name" in cmd and "kind" in cmd and "summary" in cmd
    assert cmd["kind"] in ("command", "group")
# Check root discovery is compact (no full schemas inlined)
for cmd in body["commands"]:
    assert "arguments" not in cmd, f"Root catalog inlined args for {cmd['name']}"
print("  PASS - compact root catalog, all fields present")

# 2. POST help root (Conformance #3,#4)
print()
print("--- 2. POST {command:help} (root catalog via help) [Conf #3,#4] ---")
code2, body2 = post(BASE + "/api/cli", {"command": "help"})
assert body2["status"] == "ok" and body2["interface"] == "cli"
assert body2["total"] == body["total"]
print("  Matches GET /api/cli: True")
print("  PASS")

# 3. Group help (Spec 6.2)
print()
print("--- 3. POST help 'catalog' (group help) [Spec 6.2] ---")
code3, body3 = post(
    BASE + "/api/cli", {"command": "help", "args": {"command": "catalog"}}
)
print("  status:", body3.get("status"), " kind:", body3.get("kind"))
print("  subcommands:", [s["name"] for s in body3.get("subcommands", [])])
assert body3["status"] == "ok"
assert body3["kind"] == "group"
assert "subcommands" in body3
for sub in body3["subcommands"]:
    assert "name" in sub and "kind" in sub and "summary" in sub
    assert "arguments" not in sub, f"Group help inlined args for {sub['name']}"
print("  PASS - group help is compact, no full schemas")

# 4. Command help (Spec 6.3)
print()
print("--- 4. POST help 'catalog list' (command help) [Spec 6.3] ---")
code4, body4 = post(
    BASE + "/api/cli", {"command": "help", "args": {"command": "catalog list"}}
)
print("  status:", body4.get("status"), " command:", body4.get("command"))
print("  summary:", body4.get("summary"))
print("  arguments:", [a["name"] for a in body4.get("arguments", [])])
print("  examples:", len(body4.get("examples", [])))
assert body4["status"] == "ok"
assert body4["command"] == "catalog list"
assert "arguments" in body4
for arg in body4["arguments"]:
    assert "name" in arg and "required" in arg and "default" in arg
print("  PASS - all required argument fields present")

# 5. Help unknown target (Conformance #6)
print()
print("--- 5. POST help 'bogus' (help_target_not_found) [Conf #6] ---")
code5, body5 = post(
    BASE + "/api/cli", {"command": "help", "args": {"command": "bogus"}}
)
print("  HTTP", code5, " code:", body5["error"]["code"])
assert code5 == 404
assert body5["status"] == "error"
assert body5["error"]["code"] == "help_target_not_found"
print("  PASS")

# 6. Invalid JSON (Spec 8)
print()
print("--- 6. Invalid JSON (invalid_json) [Spec 8] ---")
code6, raw6, _ = raw_post(BASE + "/api/cli", b"not json")
body6 = json.loads(raw6)
print("  HTTP", code6, " code:", body6["error"]["code"])
assert code6 == 400
assert body6["error"]["code"] == "invalid_json"
print("  PASS")

# 7. Invalid command - empty/missing (Spec 8)
print()
print("--- 7. Empty body {} (invalid_command) [Spec 8] ---")
code7, body7 = post(BASE + "/api/cli", {})
print("  HTTP", code7, " code:", body7["error"]["code"])
assert code7 == 400
assert body7["error"]["code"] == "invalid_command"
print("  PASS")

# 8. Unknown command (Conformance #7)
print()
print("--- 8. Unknown command (command_not_found) [Conf #7] ---")
code8, body8 = post(BASE + "/api/cli", {"command": "bogus_command"})
print("  HTTP", code8, " code:", body8["error"]["code"])
assert code8 == 404
assert body8["error"]["code"] == "command_not_found"
has_next = "next_actions" in body8["error"]
print("  has next_actions:", has_next)
print("  PASS")

# 9. Non-object args (Spec 8)
print()
print("--- 9. Non-object args (invalid_arguments) [Spec 8] ---")
code9, raw9, _ = raw_post(
    BASE + "/api/cli", json.dumps({"command": "health", "args": [1, 2]}).encode()
)
body9 = json.loads(raw9)
print("  HTTP", code9, " code:", body9["error"]["code"])
assert code9 == 400
assert body9["error"]["code"] == "invalid_arguments"
print("  PASS")

# 10. Missing required argument (Spec 8)
print()
print("--- 10. Missing required argument (missing_required_argument) [Spec 8] ---")
code10, body10 = post(BASE + "/api/cli", {"command": "catalog get"})
print("  HTTP", code10, " code:", body10["error"]["code"])
assert code10 == 400
assert body10["error"]["code"] == "missing_required_argument"
has_next = "next_actions" in body10["error"]
print("  has next_actions:", has_next)
if has_next:
    print("  next_actions:", body10["error"]["next_actions"])
print("  PASS")

# 11. Non-bool stream (Spec 8)
print()
print("--- 11. Non-bool stream (invalid_request) [Spec 8] ---")
code11, raw11, _ = raw_post(
    BASE + "/api/cli", json.dumps({"command": "health", "stream": "yes"}).encode()
)
body11 = json.loads(raw11)
print("  HTTP", code11, " code:", body11["error"]["code"])
assert code11 == 400
assert body11["error"]["code"] == "invalid_request"
print("  PASS")

# 12. Streaming NDJSON (Spec 9, Conformance #10)
print()
print("--- 12. Streaming NDJSON [Spec 9, Conf #10] ---")
code12, raw12, headers12 = raw_post(
    BASE + "/api/cli",
    json.dumps({"command": "catalog list", "stream": True}).encode(),
)
ct = headers12.get("Content-Type", "") if headers12 else ""
text12 = raw12.decode()
lines = [l for l in text12.strip().split("\n") if l]
first = json.loads(lines[0])
last = json.loads(lines[-1])
print("  Content-Type:", ct)
print("  Chunks:", len(lines))
print("  First chunk type:", first.get("type"))
print("  Last chunk type:", last.get("type"))
assert "ndjson" in ct.lower()
assert first["type"] == "started"
assert first["interface"] == "cli"
assert last["type"] in ("done", "result")
print("  PASS")

# 13. Invocation response shape (Spec 7, Conformance #8)
print()
print("--- 13. Invocation response shape [Spec 7, Conf #8] ---")
code13, body13 = post(BASE + "/api/cli", {"command": "health"})
print(
    "  status:",
    body13["status"],
    " interface:",
    body13["interface"],
    " version:",
    body13["version"],
)
print(
    "  command:",
    body13["command"],
    " result keys:",
    list(body13.get("result", {}).keys()),
)
assert body13["status"] == "ok"
assert body13["interface"] == "cli"
assert body13["version"] == "1.0"
assert "command" in body13
assert "result" in body13
print("  PASS")

# 14. Error response shape validation (Spec 8)
print()
print("--- 14. Error response shape validation [Spec 8] ---")
code14, body14 = post(BASE + "/api/cli", {"command": "catalog get"})
assert body14["status"] == "error"
assert body14["interface"] == "cli"
assert body14["version"] == "1.0"
assert "error" in body14
assert "code" in body14["error"]
assert "message" in body14["error"]
print(
    "  Error shape: status, interface, version, error.code, error.message all present"
)
print("  error.code is snake_case:", body14["error"]["code"])
assert body14["error"]["code"].replace("_", "").isalpha()
print("  PASS")

# 15. Help for 'help' itself
print()
print("--- 15. POST help 'help' (is help a valid help target?) ---")
code15, body15 = post(
    BASE + "/api/cli", {"command": "help", "args": {"command": "help"}}
)
print("  HTTP", code15, " status:", body15.get("status"))
if body15.get("status") == "error":
    print(
        "  code:",
        body15["error"]["code"],
        " (spec only reserves 'help' as a command, not required as a help target)",
    )
else:
    print("  help returned info about itself")
print("  PASS (by spec)")

print()
print("========================================")
print("ALL 15 CONFORMANCE TESTS PASSED")
print("========================================")
