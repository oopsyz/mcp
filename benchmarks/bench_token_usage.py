import json
import subprocess
import sys
from pathlib import Path

BASE = "http://localhost:7701"
CLI_URL = f"{BASE}/cli/tmf620/catalogmgt"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _request_raw(
    method: str, url: str, payload: dict | None = None
) -> tuple[dict, str]:
    cmd = ["curl", "-sf"]
    if method.upper() != "GET":
        cmd.extend(["-X", method.upper()])
    cmd.append(url)
    if payload is not None:
        cmd.extend(["-H", "Content-Type: application/json", "-d", json.dumps(payload)])

    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
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

def main():
    cli_catalog, cli_catalog_raw = _request_raw("POST", CLI_URL, {"command": "help"})
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
            "import json; from tmf620.server import mcp; "
            "print(json.dumps([t.model_dump() if hasattr(t, 'model_dump') else str(t) for t in mcp.tools]))",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=REPO_ROOT,
    )
    mcp_tool_defs = mcp_tool_defs_raw.stdout.strip().split("\n")[-1]
    mcp_tool_defs_json = json.loads(mcp_tool_defs)
    mcp_tool_defs_str = json.dumps(mcp_tool_defs_json)

    CLI_TOOL_TOKENS = _tokens(cli_discovery)
    MCP_TOOL_TOKENS = _tokens(mcp_tool_defs_str)

    tests = [
        ("health", {"command": "health"}, ("GET", f"{BASE}/health", None)),
        ("server-config", {"command": "config"}, ("GET", f"{BASE}/server-config", None)),
        ("catalog list", {"command": "catalog list"}, ("GET", f"{BASE}/catalogs", None)),
        (
            "catalog get",
            {"command": "catalog get", "args": {"catalog_id": "cat-001"}},
            ("GET", f"{BASE}/catalogs/cat-001", None),
        ),
        (
            "offering list",
            {"command": "offering list", "args": {"catalog_id": "cat-001"}},
            ("GET", f"{BASE}/product-offerings?catalog_id=cat-001", None),
        ),
        (
            "offering get",
            {"command": "offering get", "args": {"offering_id": "po-001"}},
            ("GET", f"{BASE}/product-offerings/po-001", None),
        ),
        (
            "specification list",
            {"command": "specification list"},
            ("GET", f"{BASE}/product-specifications", None),
        ),
        (
            "specification get",
            {"command": "specification get", "args": {"specification_id": "ps-001"}},
            ("GET", f"{BASE}/product-specifications/ps-001", None),
        ),
        (
            "offering create",
            {
                "command": "offering create",
                "args": {
                    "body": {
                        "name": "Benchmark Offer",
                        "description": "Created by benchmark",
                        "catalogId": "cat-001",
                    }
                },
            },
            (
                "POST",
                f"{BASE}/product-offerings",
                {
                    "name": "Benchmark Offer",
                    "description": "Created by benchmark",
                    "catalog_id": "cat-001",
                },
            ),
        ),
        (
            "specification create",
            {
                "command": "specification create",
                "args": {
                    "body": {
                        "name": "Benchmark Specification",
                        "description": "Created by benchmark",
                        "version": "1.0",
                    }
                },
            },
            (
                "POST",
                f"{BASE}/product-specifications",
                {
                    "name": "Benchmark Specification",
                    "description": "Created by benchmark",
                    "version": "1.0",
                },
            ),
        ),
    ]

    results = []
    for label, cli_payload, direct_request in tests:
        method, direct_url, direct_payload = direct_request
        cli_resp, cli_resp_raw = _request_raw("POST", CLI_URL, cli_payload)
        direct_resp, direct_resp_raw = _request_raw(method, direct_url, direct_payload)

        cli_req = json.dumps(cli_payload)
        direct_req = json.dumps(direct_payload) if direct_payload is not None else ""

        results.append(
            {
                "label": label,
                "cli_req": _tokens(cli_req),
                "cli_resp": _tokens(cli_resp_raw),
                "mcp_req": _tokens(direct_req),
                "mcp_resp": _tokens(direct_resp_raw),
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
    print(
        f"  {'':25s} | {'Req':>6s} {'Resp':>7s} | {'Req':>6s} {'Resp':>7s} | {'':>10s}"
    )
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
        print(
            f"  {n:>5} | {cli_cost:>10,} | {mcp_cost:>10,} | {saved:>10,} | {pct:>9.1f}%"
        )

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


if __name__ == "__main__":
    main()


