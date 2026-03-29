import json
import subprocess
import sys

BASE = "http://localhost:7701"
CLI_URL = f"{BASE}/api/cli"


def _post_raw(url: str, payload: dict) -> tuple[dict, str]:
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
    assert r.returncode == 0, f"curl failed: {r.stderr}"
    return json.loads(r.stdout), r.stdout


def _tokens(text: str) -> int:
    return max(1, len(text)) // 4


def _fmt(n: int) -> str:
    if n >= 1000:
        return f"{n:>7,}"
    return f"{n:>7}"


cli_tool_def = json.dumps(
    {
        "name": "tmf620_cli",
        "description": "TMF620 CLI dispatcher. Use help to discover commands.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to run"},
                "args": {"type": "object", "description": "Command arguments"},
            },
            "required": ["command"],
        },
    }
)

cli_catalog, cli_catalog_raw = _post_raw(CLI_URL, {"command": "help"})
cli_discovery = json.dumps(
    {
        "tool_definition": cli_tool_def,
        "help_response": cli_catalog_raw,
    }
)

mcp_tool_defs_raw = subprocess.run(
    [
        "docker",
        "compose",
        "exec",
        "tmf620-mcp",
        "python",
        "-c",
        "import json; from tmf620_mcp_server import mcp; "
        "print(json.dumps([t.model_dump() if hasattr(t, 'model_dump') else str(t) for t in mcp.tools]))",
    ],
    capture_output=True,
    text=True,
    timeout=30,
)
mcp_tool_defs = mcp_tool_defs_raw.stdout.strip().split("\n")[-1]
mcp_tool_defs_json = json.loads(mcp_tool_defs)
mcp_tool_defs_str = json.dumps(mcp_tool_defs_json)

CLI_TOOL_TOKENS = _tokens(cli_discovery)
MCP_TOOL_TOKENS = _tokens(mcp_tool_defs_str)

tests = [
    ("health", {"command": "health"}, f"{BASE}/commands/health", {"args": {}}),
    ("config", {"command": "config"}, f"{BASE}/commands/config", {"args": {}}),
    (
        "catalog list",
        {"command": "catalog list"},
        f"{BASE}/commands/catalog/list",
        {"args": {}},
    ),
    (
        "catalog list (limit=1)",
        {"command": "catalog list", "args": {"limit": 1}},
        f"{BASE}/commands/catalog/list",
        {"args": {"limit": 1}},
    ),
    (
        "catalog get",
        {"command": "catalog get", "args": {"catalog_id": "cat-001"}},
        f"{BASE}/commands/catalog/get",
        {"args": {"catalog_id": "cat-001"}},
    ),
    (
        "offering list",
        {"command": "offering list"},
        f"{BASE}/commands/offering/list",
        {"args": {}},
    ),
    (
        "offering get",
        {"command": "offering get", "args": {"offering_id": "po-001"}},
        f"{BASE}/commands/offering/get",
        {"args": {"offering_id": "po-001"}},
    ),
    (
        "category list",
        {"command": "category list"},
        f"{BASE}/commands/category/list",
        {"args": {}},
    ),
    (
        "category get",
        {"command": "category get", "args": {"category_id": "category-internet"}},
        f"{BASE}/commands/category/get",
        {"args": {"category_id": "category-internet"}},
    ),
    (
        "specification list",
        {"command": "specification list"},
        f"{BASE}/commands/specification/list",
        {"args": {}},
    ),
    (
        "specification get",
        {"command": "specification get", "args": {"specification_id": "ps-001"}},
        f"{BASE}/commands/specification/get",
        {"args": {"specification_id": "ps-001"}},
    ),
    (
        "price list",
        {"command": "price list"},
        f"{BASE}/commands/price/list",
        {"args": {}},
    ),
    (
        "price get",
        {"command": "price get", "args": {"price_id": "pop-001"}},
        f"{BASE}/commands/price/get",
        {"args": {"price_id": "pop-001"}},
    ),
    (
        "import-job list",
        {"command": "import-job list"},
        f"{BASE}/commands/import-job/list",
        {"args": {}},
    ),
    (
        "export-job list",
        {"command": "export-job list"},
        f"{BASE}/commands/export-job/list",
        {"args": {}},
    ),
    (
        "hub create",
        {
            "command": "hub create",
            "args": {"body": {"callback": "http://localhost:9999/hook"}},
        },
        f"{BASE}/commands/hub/create",
        {"args": {"body": {"callback": "http://localhost:9999/hook"}}},
    ),
]

results = []
for label, cli_payload, mcp_url, mcp_payload in tests:
    cli_resp, cli_resp_raw = _post_raw(CLI_URL, cli_payload)
    mcp_resp, mcp_resp_raw = _post_raw(mcp_url, mcp_payload)

    cli_req = json.dumps(cli_payload)
    mcp_req = json.dumps(mcp_payload)

    results.append(
        {
            "label": label,
            "cli_req": _tokens(cli_req),
            "cli_resp": _tokens(cli_resp_raw),
            "mcp_req": _tokens(mcp_req),
            "mcp_resp": _tokens(mcp_resp_raw),
        }
    )

print("=" * 95)
print("Full Token Cost Analysis: CLI vs MCP (from LLM perspective)")
print("=" * 95)

print(f"\n  Tool definitions (sent EVERY LLM turn):")
print(
    f"    CLI:  {len(cli_discovery):>6,} chars  ~{_tokens(cli_discovery):>5,} tokens  (1 tool + help catalog)"
)
print(
    f"    MCP:  {len(mcp_tool_defs_str):>6,} chars  ~{_tokens(mcp_tool_defs_str):>5,} tokens  ({len(mcp_tool_defs_json)} tool schemas)"
)
print(
    f"    CLI saves: ~{MCP_TOOL_TOKENS - CLI_TOOL_TOKENS:,} tokens/turn on tool definitions"
)

print(f"\n{'Per-operation (payload only):':}")
print(f"  {'Operation':<25s} | {'CLI':^14s} | {'MCP':^14s} | {'CLI saves':>10s}")
print(f"  {'':25s} | {'Req':>6s} {'Resp':>7s} | {'Req':>6s} {'Resp':>7s} | {'':>10s}")
print(f"  {'-' * 80}")

total_cli_payload = 0
total_mcp_payload = 0
for r in results:
    cli_total = r["cli_req"] + r["cli_resp"]
    mcp_total = r["mcp_req"] + r["mcp_resp"]
    total_cli_payload += cli_total
    total_mcp_payload += mcp_total
    savings = cli_total - mcp_total
    sign = "+" if savings > 0 else "" if savings < 0 else " "
    print(
        f"  {r['label']:<25s} | {_fmt(r['cli_req'])} {_fmt(r['cli_resp'])} | {_fmt(r['mcp_req'])} {_fmt(r['mcp_resp'])} | {sign}{savings:>8}"
    )

print(f"  {'-' * 80}")
print(
    f"  {'TOTAL (payload)':<25s} | {'':>6s} {'':>7s} | {'':>6s} {'':>7s} | {total_cli_payload - total_mcp_payload:>9}"
)

print(f"\n{'=' * 95}")
print(f"Full session cost = tool_defs × N_turns + payload_per_turn × N_turns")
print(f"{'=' * 95}")

print(
    f"\n  {'Turns':>5s} | {'CLI total':>10s} | {'MCP total':>10s} | {'CLI saves':>10s} | {'Savings %':>10s}"
)
print(f"  {'-' * 55}")

for n in [1, 5, 10, 20, 50]:
    cli_cost = CLI_TOOL_TOKENS * n + total_cli_payload * n
    mcp_cost = MCP_TOOL_TOKENS * n + total_mcp_payload * n
    saved = mcp_cost - cli_cost
    pct = (saved / mcp_cost) * 100
    print(f"  {n:>5} | {cli_cost:>10,} | {mcp_cost:>10,} | {saved:>10,} | {pct:>9.1f}%")

print(f"\n{'=' * 95}")
print(f"Analysis")
print(f"{'=' * 95}")
print(
    f"  CLI tool overhead:  ~{CLI_TOOL_TOKENS:,} tokens/turn  (1 dispatcher + catalog)"
)
print(
    f"  MCP tool overhead:  ~{MCP_TOOL_TOKENS:,} tokens/turn  ({len(mcp_tool_defs_json)} separate tools)"
)
print(
    f"  CLI envelope cost:  ~{total_cli_payload - total_mcp_payload} tokens/call more on payload"
)
print(
    f"  CLI net savings:    ~{MCP_TOOL_TOKENS - CLI_TOOL_TOKENS:,} tokens/turn (tool def savings >> envelope cost)"
)
print(f"{'=' * 95}")
