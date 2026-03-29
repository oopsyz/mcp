from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import tiktoken

from tmf620_commands import COMMAND_TREE, get_catalog_payload, get_command_help_payload


BASE = "http://localhost:7701"
CLI_URL = f"{BASE}/api/cli"
DEFAULT_ENCODING = "cl100k_base"
DEFAULT_ITERATIONS = 50


def _post(url: str, payload: dict[str, Any], *, allow_error: bool = False) -> float:
    start = time.perf_counter()
    cmd = [
        "curl",
        "-s",
        "-X",
        "POST",
        url,
        "-H",
        "Content-Type: application/json",
        "-d",
        json.dumps(payload),
    ]
    if not allow_error:
        cmd.insert(1, "-f")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    elapsed = time.perf_counter() - start
    if not allow_error:
        assert r.returncode == 0, f"curl failed: {r.stderr}"
    return elapsed


def run_latency_benchmark(iterations: int = DEFAULT_ITERATIONS) -> dict[str, list[float]]:
    results: dict[str, list[float]] = {}

    def _bench(
        label: str,
        url: str,
        payload: dict[str, Any],
        *,
        allow_error: bool = False,
    ) -> None:
        print(f"  {label} ({iterations} calls)...", end=" ", flush=True)
        latencies: list[float] = []
        for _ in range(iterations):
            t = _post(url, payload, allow_error=allow_error)
            latencies.append(t)
        results[label] = latencies
        mean = statistics.mean(latencies) * 1000
        med = statistics.median(latencies) * 1000
        p95_index = max(0, math.ceil(0.95 * len(latencies)) - 1)
        p95 = sorted(latencies)[p95_index] * 1000
        print(f"mean={mean:.1f}ms  median={med:.1f}ms  p95={p95:.1f}ms")

    def _print_comparison(cli_label: str, mcp_label: str) -> None:
        cli_ms = statistics.mean(results[cli_label]) * 1000
        mcp_ms = statistics.mean(results[mcp_label]) * 1000
        if cli_ms < mcp_ms:
            print(f"    --> CLI is {mcp_ms / cli_ms:.2f}x faster")
        else:
            print(f"    --> MCP is {cli_ms / mcp_ms:.2f}x faster")

    print("=" * 70)
    print(f"CLI vs MCP Benchmark  ({iterations} iterations per test)")
    print("=" * 70)

    print("\n-- catalog list --")
    _bench("cli: catalog list", CLI_URL, {"command": "catalog list"})
    _bench("mcp: catalog list", f"{BASE}/commands/catalog/list", {"args": {}})
    _print_comparison("cli: catalog list", "mcp: catalog list")

    print("\n-- catalog get --")
    _bench(
        "cli: catalog get",
        CLI_URL,
        {"command": "catalog get", "args": {"catalog_id": "cat-001"}},
    )
    _bench(
        "mcp: catalog get",
        f"{BASE}/commands/catalog/get",
        {"args": {"catalog_id": "cat-001"}},
    )
    _print_comparison("cli: catalog get", "mcp: catalog get")

    print("\n-- offering list --")
    _bench("cli: offering list", CLI_URL, {"command": "offering list"})
    _bench("mcp: offering list", f"{BASE}/commands/offering/list", {"args": {}})
    _print_comparison("cli: offering list", "mcp: offering list")

    print("\n-- offering get --")
    _bench(
        "cli: offering get",
        CLI_URL,
        {"command": "offering get", "args": {"offering_id": "po-001"}},
    )
    _bench(
        "mcp: offering get",
        f"{BASE}/commands/offering/get",
        {"args": {"offering_id": "po-001"}},
    )
    _print_comparison("cli: offering get", "mcp: offering get")

    print("\n-- category list --")
    _bench("cli: category list", CLI_URL, {"command": "category list"})
    _bench("mcp: category list", f"{BASE}/commands/category/list", {"args": {}})
    _print_comparison("cli: category list", "mcp: category list")

    print("\n-- specification list --")
    _bench("cli: spec list", CLI_URL, {"command": "specification list"})
    _bench("mcp: spec list", f"{BASE}/commands/specification/list", {"args": {}})
    _print_comparison("cli: spec list", "mcp: spec list")

    print("\n-- price list --")
    _bench("cli: price list", CLI_URL, {"command": "price list"})
    _bench("mcp: price list", f"{BASE}/commands/price/list", {"args": {}})
    _print_comparison("cli: price list", "mcp: price list")

    print("\n-- health --")
    _bench("cli: health", CLI_URL, {"command": "health"})
    _bench("mcp: health", f"{BASE}/commands/health", {"args": {}})
    _print_comparison("cli: health", "mcp: health")

    print("\n-- config --")
    _bench("cli: config", CLI_URL, {"command": "config"})
    _bench("mcp: config", f"{BASE}/commands/config", {"args": {}})
    _print_comparison("cli: config", "mcp: config")

    print("\n-- validation error (missing arg) --")
    _bench(
        "cli: err missing arg",
        CLI_URL,
        {"command": "catalog get"},
        allow_error=True,
    )
    _bench(
        "mcp: err missing arg",
        f"{BASE}/commands/catalog/get",
        {"args": {}},
        allow_error=True,
    )
    _print_comparison("cli: err missing arg", "mcp: err missing arg")

    print("\n-- validation error (unknown arg) --")
    _bench(
        "cli: err unknown arg",
        CLI_URL,
        {"command": "health", "args": {"bogus": 1}},
        allow_error=True,
    )
    _bench(
        "mcp: err unknown arg",
        f"{BASE}/commands/health",
        {"args": {"bogus": 1}},
        allow_error=True,
    )
    _print_comparison("cli: err unknown arg", "mcp: err unknown arg")

    print("\n" + "=" * 70)
    print("Summary (mean ms)")
    print("-" * 70)
    print(f"{'Test':<30s} {'CLI':>8s} {'MCP':>8s} {'Ratio':>8s}")
    print("-" * 70)
    cli_tests = [k for k in results if k.startswith("cli:")]
    for cli_key in cli_tests:
        mcp_key = cli_key.replace("cli:", "mcp:")
        if mcp_key not in results:
            continue
        cli_ms = statistics.mean(results[cli_key]) * 1000
        mcp_ms = statistics.mean(results[mcp_key]) * 1000
        ratio = mcp_ms / cli_ms if cli_ms > 0 else 0
        label = cli_key.replace("cli: ", "")
        print(f"{label:<30s} {cli_ms:>7.1f}ms {mcp_ms:>7.1f}ms {ratio:>7.2f}x")
    print("=" * 70)
    return results


def _dump(payload: Any) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _token_count(encoding_name: str, payload: Any) -> tuple[int, int]:
    dumped = _dump(payload)
    encoded = tiktoken.get_encoding(encoding_name).encode(dumped)
    return len(dumped), len(encoded)


def _iter_command_paths(
    nodes: list[dict[str, Any]], prefix: tuple[str, ...] = ()
) -> list[list[str]]:
    paths: list[list[str]] = []
    for node in nodes:
        path = (*prefix, node["name"])
        if node["kind"] == "command":
            paths.append(list(path))
            continue
        paths.extend(_iter_command_paths(node.get("commands", []), path))
    return paths


def _schema_type(type_name: Any) -> str:
    if type_name in {"integer", "number", "boolean", "array", "object"}:
        return type_name
    return "string"


def _tool_snapshot_from_command_tree() -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for path in _iter_command_paths(COMMAND_TREE):
        help_payload = get_command_help_payload(" ".join(path))
        if help_payload is None:
            continue

        properties: dict[str, Any] = {}
        required: list[str] = []
        for argument in help_payload.get("arguments", []):
            arg_name = argument["name"]
            properties[arg_name] = {
                "type": _schema_type(argument.get("type")),
                "description": argument.get("description", ""),
            }
            if argument.get("default") is not None:
                properties[arg_name]["default"] = argument["default"]
            if argument.get("enum"):
                properties[arg_name]["enum"] = argument["enum"]
            if argument.get("required"):
                required.append(arg_name)

        tools.append(
            {
                "name": "_".join(path),
                "description": help_payload.get("summary", ""),
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                    "additionalProperties": False,
                },
            }
        )
    return tools


def build_report(encoding_name: str = DEFAULT_ENCODING) -> dict[str, Any]:
    raw_tools = _tool_snapshot_from_command_tree()
    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get(
                    "inputSchema", {"type": "object", "properties": {}}
                ),
                "strict": True,
            },
        }
        for tool in raw_tools
    ]

    compact_catalog = get_catalog_payload()
    compact_group_help = get_command_help_payload("offering")
    leaf_help = get_command_help_payload("offering patch")

    compact_catalog_chars, compact_catalog_tokens = _token_count(
        encoding_name, compact_catalog
    )
    compact_group_chars, compact_group_tokens = _token_count(
        encoding_name, compact_group_help
    )
    leaf_chars, leaf_tokens = _token_count(encoding_name, leaf_help)
    raw_mcp_chars, raw_mcp_tokens = _token_count(encoding_name, {"tools": raw_tools})
    openai_mcp_chars, openai_mcp_tokens = _token_count(
        encoding_name, {"tools": openai_tools}
    )

    return {
        "encoding": encoding_name,
        "mcp": {
            "tool_count": len(raw_tools),
            "raw_tools_payload": {
                "chars": raw_mcp_chars,
                "tokens": raw_mcp_tokens,
            },
            "openai_wrapped_tools_payload": {
                "chars": openai_mcp_chars,
                "tokens": openai_mcp_tokens,
            },
        },
        "cli_http": {
            "compact_catalog": {
                "chars": compact_catalog_chars,
                "tokens": compact_catalog_tokens,
            },
            "compact_group_help": {
                "chars": compact_group_chars,
                "tokens": compact_group_tokens,
            },
            "leaf_help": {
                "chars": leaf_chars,
                "tokens": leaf_tokens,
            },
            "progressive_catalog_plus_group": {
                "chars": compact_catalog_chars + compact_group_chars,
                "tokens": compact_catalog_tokens + compact_group_tokens,
            },
            "progressive_catalog_plus_group_plus_leaf": {
                "chars": compact_catalog_chars + compact_group_chars + leaf_chars,
                "tokens": compact_catalog_tokens + compact_group_tokens + leaf_tokens,
            },
        },
        "ratios": {
            "openai_mcp_vs_compact_catalog": round(
                openai_mcp_tokens / compact_catalog_tokens, 2
            ),
            "openai_mcp_vs_progressive_to_leaf": round(
                openai_mcp_tokens
                / (compact_catalog_tokens + compact_group_tokens + leaf_tokens),
                2,
            ),
        },
    }


def _metric_paths() -> list[tuple[str, ...]]:
    return [
        ("mcp", "tool_count"),
        ("mcp", "raw_tools_payload", "tokens"),
        ("mcp", "openai_wrapped_tools_payload", "tokens"),
        ("cli_http", "compact_catalog", "tokens"),
        ("cli_http", "compact_group_help", "tokens"),
        ("cli_http", "leaf_help", "tokens"),
        ("cli_http", "progressive_catalog_plus_group", "tokens"),
        ("cli_http", "progressive_catalog_plus_group_plus_leaf", "tokens"),
        ("ratios", "openai_mcp_vs_compact_catalog"),
        ("ratios", "openai_mcp_vs_progressive_to_leaf"),
    ]


def _get_nested_value(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = payload
    for key in path:
        current = current[key]
    return current


def _compare_reports(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    comparisons: list[dict[str, Any]] = []
    for path in _metric_paths():
        current_value = _get_nested_value(current, path)
        baseline_value = _get_nested_value(baseline, path)
        delta = current_value - baseline_value
        percent = None
        if baseline_value not in (0, 0.0):
            percent = round((delta / baseline_value) * 100, 2)
        comparisons.append(
            {
                "path": ".".join(path),
                "baseline": baseline_value,
                "current": current_value,
                "delta": delta,
                "delta_percent": percent,
            }
        )
    return {
        "baseline_encoding": baseline.get("encoding"),
        "current_encoding": current.get("encoding"),
        "comparisons": comparisons,
    }


def _format_compare_table(compare: dict[str, Any]) -> str:
    rows = compare["comparisons"]
    headers = ["metric", "baseline", "current", "delta", "delta %"]
    formatted_rows: list[list[str]] = []
    for row in rows:
        delta_percent = row["delta_percent"]
        formatted_rows.append(
            [
                row["path"],
                str(row["baseline"]),
                str(row["current"]),
                str(row["delta"]),
                "n/a" if delta_percent is None else f"{delta_percent:.2f}%",
            ]
        )

    widths = [len(header) for header in headers]
    for row in formatted_rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    def render_row(values: list[str]) -> str:
        return "  ".join(values[idx].ljust(widths[idx]) for idx in range(len(values)))

    lines = [render_row(headers), render_row(["-" * width for width in widths])]
    for row in formatted_rows:
        lines.append(render_row(row))

    return "\n".join(lines)


def main_token(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare token usage for the compact HTTP CLI discovery flow versus "
            "the MCP tool surface exposed by this repo."
        )
    )
    parser.add_argument(
        "--encoding",
        default=DEFAULT_ENCODING,
        help=f"Tokenizer encoding name to use. Default: {DEFAULT_ENCODING}.",
    )
    parser.add_argument(
        "--output",
        choices=("json", "pretty"),
        default="pretty",
        help="Output format.",
    )
    parser.add_argument(
        "--baseline",
        help="Optional path to a previous JSON report to compare against.",
    )
    args = parser.parse_args(argv)

    report = build_report(args.encoding)
    if args.baseline:
        baseline_path = Path(args.baseline)
        baseline_report = json.loads(baseline_path.read_text(encoding="utf-8"))
        compare = _compare_reports(report, baseline_report)
        if args.output == "json":
            report = {
                "current": report,
                "baseline": baseline_report,
                "compare": compare,
            }
        else:
            print(_format_compare_table(compare))
            return

    if args.output == "json":
        print(json.dumps(report, separators=(",", ":"), sort_keys=True))
        return

    print(json.dumps(report, indent=2))


def main_latency(argv: list[str] | None = None) -> None:
    iterations = int(argv[0]) if argv else DEFAULT_ITERATIONS
    run_latency_benchmark(iterations)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run the TMF620 benchmark suite."
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    token_parser = subparsers.add_parser("token", help="Run the token benchmark")
    token_parser.add_argument(
        "--encoding",
        default=DEFAULT_ENCODING,
        help=f"Tokenizer encoding name to use. Default: {DEFAULT_ENCODING}.",
    )
    token_parser.add_argument(
        "--output",
        choices=("json", "pretty"),
        default="pretty",
        help="Output format.",
    )
    token_parser.add_argument(
        "--baseline",
        help="Optional path to a previous JSON report to compare against.",
    )

    latency_parser = subparsers.add_parser(
        "latency", help="Run the latency benchmark"
    )
    latency_parser.add_argument(
        "iterations",
        nargs="?",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f"Number of iterations per test. Default: {DEFAULT_ITERATIONS}.",
    )

    args = parser.parse_args(argv)

    if args.mode == "token":
        token_args: list[str] = []
        if args.encoding != DEFAULT_ENCODING:
            token_args.extend(["--encoding", args.encoding])
        if args.output != "pretty":
            token_args.extend(["--output", args.output])
        if args.baseline:
            token_args.extend(["--baseline", args.baseline])
        main_token(token_args)
        return

    if args.mode == "latency":
        main_latency([str(args.iterations)])
        return


if __name__ == "__main__":
    main(sys.argv[1:])
