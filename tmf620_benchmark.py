from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any
import os

import requests
import tiktoken
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from tmf620_commands import _tool_name, get_catalog_payload, get_command_help_payload


BASE = os.environ.get("TMF620_BASE_URL", "http://localhost:7701").rstrip("/")
CLI_URL = f"{BASE}/cli/tmf620/catalogmgt"
DEFAULT_ENCODING = "cl100k_base"
DEFAULT_ITERATIONS = 50
DEFAULT_OUTPUT = "pretty"

LATENCY_TESTS: list[dict[str, Any]] = [
    {
        "label": "catalog list",
        "cli_payload": {"command": "catalog list"},
        "mcp_segments": ("catalog", "list"),
        "mcp_payload": {},
    },
    {
        "label": "catalog get",
        "cli_payload": {"command": "catalog get", "args": {"catalog_id": "cat-001"}},
        "mcp_segments": ("catalog", "get"),
        "mcp_payload": {"catalog_id": "cat-001"},
    },
    {
        "label": "offering list",
        "cli_payload": {"command": "offering list"},
        "mcp_segments": ("offering", "list"),
        "mcp_payload": {},
    },
    {
        "label": "offering get",
        "cli_payload": {"command": "offering get", "args": {"offering_id": "po-001"}},
        "mcp_segments": ("offering", "get"),
        "mcp_payload": {"offering_id": "po-001"},
    },
    {
        "label": "category list",
        "cli_payload": {"command": "category list"},
        "mcp_segments": ("category", "list"),
        "mcp_payload": {},
    },
    {
        "label": "specification list",
        "cli_payload": {"command": "specification list"},
        "mcp_segments": ("specification", "list"),
        "mcp_payload": {},
    },
    {
        "label": "price list",
        "cli_payload": {"command": "price list"},
        "mcp_segments": ("price", "list"),
        "mcp_payload": {},
    },
    {
        "label": "health",
        "cli_payload": {"command": "health"},
        "mcp_segments": ("health",),
        "mcp_payload": {},
    },
    {
        "label": "config",
        "cli_payload": {"command": "config"},
        "mcp_segments": ("config",),
        "mcp_payload": {},
    },
    {
        "label": "err missing arg",
        "cli_payload": {"command": "catalog get"},
        "mcp_segments": ("catalog", "get"),
        "mcp_payload": {},
        "allow_error": True,
    },
    {
        "label": "err unknown arg",
        "cli_payload": {"command": "health", "args": {"bogus": 1}},
        "mcp_segments": ("health",),
        "mcp_payload": {"bogus": 1},
        "allow_error": True,
    },
]


def _has_error_payload(payload: Any) -> bool:
    return isinstance(payload, dict) and (
        payload.get("status") == "error" or "error" in payload
    )


def _post(
    session: requests.Session,
    url: str,
    payload: dict[str, Any],
    *,
    allow_error: bool = False,
) -> tuple[float, dict[str, Any] | None]:
    start = time.perf_counter()
    response = session.post(url, json=payload, timeout=30)
    elapsed = time.perf_counter() - start

    if not allow_error:
        response.raise_for_status()

    body: dict[str, Any] | None = None
    try:
        body = response.json()
    except ValueError:
        body = None

    if not allow_error and _has_error_payload(body):
        raise AssertionError(f"unexpected error payload from {url}: {body}")

    if not allow_error and body is None:
        raise AssertionError(f"expected JSON response from {url}")

    return elapsed, body


def _get(
    session: requests.Session,
    url: str,
    *,
    allow_error: bool = False,
) -> tuple[float, dict[str, Any] | None]:
    start = time.perf_counter()
    response = session.get(url, timeout=30)
    elapsed = time.perf_counter() - start

    if not allow_error:
        response.raise_for_status()

    body: dict[str, Any] | None = None
    try:
        body = response.json()
    except ValueError:
        body = None

    if not allow_error and _has_error_payload(body):
        raise AssertionError(f"unexpected error payload from {url}: {body}")

    if not allow_error and body is None:
        raise AssertionError(f"expected JSON response from {url}")

    return elapsed, body


def _percentile(latencies: list[float], percentile: float) -> float:
    if not latencies:
        raise ValueError("latencies must not be empty")
    ordered = sorted(latencies)
    index = min(len(ordered) - 1, max(0, math.ceil(percentile * len(ordered)) - 1))
    return ordered[index]


def _latency_stats(latencies: list[float]) -> dict[str, float]:
    return {
        "mean_ms": statistics.mean(latencies) * 1000,
        "median_ms": statistics.median(latencies) * 1000,
        "p95_ms": _percentile(latencies, 0.95) * 1000,
    }


def run_latency_benchmark(
    iterations: int = DEFAULT_ITERATIONS,
    *,
    verbose: bool = True,
    warmup: int = 1,
    cold_start: bool = False,
) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        http_session = requests.Session()

        def _cli_discovery_commands(segments: tuple[str, ...]) -> list[str]:
            if len(segments) <= 1:
                return [" ".join(segments)]
            return [segments[0], " ".join(segments)]

        async def _bench_http(
            *,
            label: str,
            url: str,
            payload: dict[str, Any],
            discovery_commands: list[str],
            allow_error: bool = False,
        ) -> dict[str, Any]:
            if verbose:
                print(f"  {label} ({iterations} calls)...", end=" ", flush=True)
            latencies: list[float] = []
            for _ in range(iterations):
                start = time.perf_counter()
                _get(http_session, url, allow_error=allow_error)
                for command in discovery_commands:
                    _post(
                        http_session,
                        url,
                        {"command": "help", "args": {"command": command}},
                        allow_error=allow_error,
                    )
                _post(http_session, url, payload, allow_error=allow_error)
                elapsed = time.perf_counter() - start
                latencies.append(elapsed)
            stats = _latency_stats(latencies)
            result = {
                "label": label,
                "url": url,
                "allow_error": allow_error,
                "iterations": iterations,
                "latencies_ms": [round(latency * 1000, 3) for latency in latencies],
                **stats,
            }
            if verbose:
                print(
                    f"mean={stats['mean_ms']:.1f}ms  "
                    f"median={stats['median_ms']:.1f}ms  "
                    f"p95={stats['p95_ms']:.1f}ms"
                )
            return result

        async def _bench_mcp(
            *,
            session: ClientSession | None,
            label: str,
            tool_name: str,
            args: dict[str, Any],
            allow_error: bool = False,
            warmup_calls: int = warmup,
            cold_start: bool = cold_start,
        ) -> dict[str, Any]:
            if verbose:
                print(f"  {label} ({iterations} calls)...", end=" ", flush=True)
            latencies: list[float] = []
            if cold_start:
                for _ in range(warmup_calls):
                    async with streamablehttp_client(f"{BASE}/mcp") as (read, write, _):
                        async with ClientSession(read, write) as fresh_session:
                            await fresh_session.initialize()
                            available = {
                                tool.name for tool in (await fresh_session.list_tools()).tools
                            }
                            if tool_name not in available:
                                raise AssertionError(
                                    f"expected MCP tool {tool_name!r} to be available; got {sorted(available)!r}"
                                )
                            warmup_result = await fresh_session.call_tool(tool_name, args)
                            if not allow_error and getattr(warmup_result, "isError", False):
                                raise AssertionError(
                                    f"unexpected warm-up error result from {tool_name}: {warmup_result}"
                                )
                for _ in range(iterations):
                    start = time.perf_counter()
                    async with streamablehttp_client(f"{BASE}/mcp") as (read, write, _):
                        async with ClientSession(read, write) as fresh_session:
                            await fresh_session.initialize()
                            available = {
                                tool.name for tool in (await fresh_session.list_tools()).tools
                            }
                            if tool_name not in available:
                                raise AssertionError(
                                    f"expected MCP tool {tool_name!r} to be available; got {sorted(available)!r}"
                                )
                            result = await fresh_session.call_tool(tool_name, args)
                    elapsed = time.perf_counter() - start
                    if not allow_error and getattr(result, "isError", False):
                        raise AssertionError(
                            f"unexpected error result from {tool_name}: {result}"
                        )
                    latencies.append(elapsed)
            else:
                assert session is not None
                for _ in range(warmup_calls):
                    available = {tool.name for tool in (await session.list_tools()).tools}
                    if tool_name not in available:
                        raise AssertionError(
                            f"expected MCP tool {tool_name!r} to be available; got {sorted(available)!r}"
                        )
                    warmup_result = await session.call_tool(tool_name, args)
                    if not allow_error and getattr(warmup_result, "isError", False):
                        raise AssertionError(
                            f"unexpected warm-up error result from {tool_name}: {warmup_result}"
                        )
                for _ in range(iterations):
                    start = time.perf_counter()
                    available = {tool.name for tool in (await session.list_tools()).tools}
                    if tool_name not in available:
                        raise AssertionError(
                            f"expected MCP tool {tool_name!r} to be available; got {sorted(available)!r}"
                        )
                    result = await session.call_tool(tool_name, args)
                    elapsed = time.perf_counter() - start
                    if not allow_error and getattr(result, "isError", False):
                        raise AssertionError(
                            f"unexpected error result from {tool_name}: {result}"
                        )
                    latencies.append(elapsed)
            stats = _latency_stats(latencies)
            result = {
                "label": label,
                "tool": tool_name,
                "allow_error": allow_error,
                "iterations": iterations,
                "cold_start": cold_start,
                "latencies_ms": [round(latency * 1000, 3) for latency in latencies],
                **stats,
            }
            if verbose:
                print(
                    f"mean={stats['mean_ms']:.1f}ms  "
                    f"median={stats['median_ms']:.1f}ms  "
                    f"p95={stats['p95_ms']:.1f}ms"
                )
            return result

        def _print_comparison(
            cli_result: dict[str, Any], mcp_result: dict[str, Any]
        ) -> None:
            cli_ms = cli_result["mean_ms"]
            mcp_ms = mcp_result["mean_ms"]
            if cli_ms < mcp_ms:
                print(f"    --> CLI is {mcp_ms / cli_ms:.2f}x faster")
            else:
                print(f"    --> MCP is {cli_ms / mcp_ms:.2f}x faster")

        try:
            if verbose:
                print("=" * 70)
                print(
                    f"End-user CLI vs MCP Benchmark  ({iterations} iterations per test)"
                )
                if cold_start:
                    print("Mode: cold-start MCP sessions; fresh connection per iteration")
                print("=" * 70)

            if cold_start:
                for test in LATENCY_TESTS:
                    cli_result = await _bench_http(
                        label=f"cli: {test['label']}",
                        url=CLI_URL,
                        payload=test["cli_payload"],
                        discovery_commands=_cli_discovery_commands(
                            test["mcp_segments"]
                        ),
                        allow_error=test.get("allow_error", False),
                    )
                    mcp_result = await _bench_mcp(
                        session=None,
                        label=f"mcp: {test['label']}",
                        tool_name=_tool_name(*test["mcp_segments"]),
                        args=test["mcp_payload"],
                        allow_error=test.get("allow_error", False),
                        cold_start=True,
                    )
                    results.extend([cli_result, mcp_result])
                    if verbose:
                        _print_comparison(cli_result, mcp_result)
            else:
                async with streamablehttp_client(f"{BASE}/mcp") as (read, write, _):
                    async with ClientSession(read, write) as mcp_session:
                        await mcp_session.initialize()
                        for test in LATENCY_TESTS:
                            cli_result = await _bench_http(
                                label=f"cli: {test['label']}",
                                url=CLI_URL,
                                payload=test["cli_payload"],
                                discovery_commands=_cli_discovery_commands(
                                    test["mcp_segments"]
                                ),
                                allow_error=test.get("allow_error", False),
                            )
                            mcp_result = await _bench_mcp(
                                session=mcp_session,
                                label=f"mcp: {test['label']}",
                                tool_name=_tool_name(*test["mcp_segments"]),
                                args=test["mcp_payload"],
                                allow_error=test.get("allow_error", False),
                            )
                            results.extend([cli_result, mcp_result])
                            if verbose:
                                _print_comparison(cli_result, mcp_result)

            comparisons: list[dict[str, Any]] = []
            cli_results = [row for row in results if row["label"].startswith("cli:")]
            for cli_result in cli_results:
                mcp_result = next(
                    row
                    for row in results
                    if row["label"] == cli_result["label"].replace("cli:", "mcp:")
                )
                comparisons.append(
                    {
                        "label": cli_result["label"].removeprefix("cli: "),
                        "cli_mean_ms": cli_result["mean_ms"],
                        "mcp_mean_ms": mcp_result["mean_ms"],
                        "ratio": round(mcp_result["mean_ms"] / cli_result["mean_ms"], 2),
                    }
                )

            if verbose:
                print("\n" + "=" * 70)
                print("Summary (mean ms)")
                print("-" * 70)
                print(f"{'Test':<30s} {'CLI':>8s} {'MCP':>8s} {'Ratio':>8s}")
                print("-" * 70)
                for row in comparisons:
                    print(
                        f"{row['label']:<30s} "
                        f"{row['cli_mean_ms']:>7.1f}ms "
                        f"{row['mcp_mean_ms']:>7.1f}ms "
                        f"{row['ratio']:>7.2f}x"
                    )
                print("=" * 70)

            return {
                "iterations": iterations,
                "cold_start": cold_start,
                "tests": results,
                "comparisons": comparisons,
            }
        finally:
            http_session.close()

    return asyncio.run(_run())


def _dump(payload: Any) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _token_count(encoding_name: str, payload: Any) -> tuple[int, int]:
    dumped = _dump(payload)
    encoded = tiktoken.get_encoding(encoding_name).encode(dumped)
    return len(dumped), len(encoded)


async def _fetch_live_mcp_tools() -> list[dict[str, Any]]:
    async with streamablehttp_client(f"{BASE}/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            return [tool.model_dump(mode="json") for tool in tools.tools]


def build_report(encoding_name: str = DEFAULT_ENCODING) -> dict[str, Any]:
    raw_tools = asyncio.run(_fetch_live_mcp_tools())
    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema", {"type": "object"}),
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
        "mcp_tool_surface": {
            "tool_count": len(raw_tools),
            "raw_tool_list_payload": {
                "chars": raw_mcp_chars,
                "tokens": raw_mcp_tokens,
            },
            "openai_wrapped_tool_surface_payload": {
                "chars": openai_mcp_chars,
                "tokens": openai_mcp_tokens,
            },
        },
        "http_cli_discovery": {
            "compact_catalog_payload": {
                "chars": compact_catalog_chars,
                "tokens": compact_catalog_tokens,
            },
            "compact_group_help_payload": {
                "chars": compact_group_chars,
                "tokens": compact_group_tokens,
            },
            "leaf_help_payload": {
                "chars": leaf_chars,
                "tokens": leaf_tokens,
            },
            "progressive_catalog_plus_group_payload": {
                "chars": compact_catalog_chars + compact_group_chars,
                "tokens": compact_catalog_tokens + compact_group_tokens,
            },
            "progressive_catalog_plus_group_plus_leaf_payload": {
                "chars": compact_catalog_chars + compact_group_chars + leaf_chars,
                "tokens": compact_catalog_tokens + compact_group_tokens + leaf_tokens,
            },
        },
        "ratios": {
            "openai_wrapped_mcp_vs_compact_catalog_payload": round(
                openai_mcp_tokens / compact_catalog_tokens, 2
            ),
            "openai_wrapped_mcp_vs_progressive_to_leaf_payload": round(
                openai_mcp_tokens
                / (compact_catalog_tokens + compact_group_tokens + leaf_tokens),
                2,
            ),
        },
    }


def _metric_paths() -> list[tuple[str, ...]]:
    return [
        ("mcp_tool_surface", "tool_count"),
        ("mcp_tool_surface", "raw_tool_list_payload", "tokens"),
        ("mcp_tool_surface", "openai_wrapped_tool_surface_payload", "tokens"),
        ("http_cli_discovery", "compact_catalog_payload", "tokens"),
        ("http_cli_discovery", "compact_group_help_payload", "tokens"),
        ("http_cli_discovery", "leaf_help_payload", "tokens"),
        ("http_cli_discovery", "progressive_catalog_plus_group_payload", "tokens"),
        (
            "http_cli_discovery",
            "progressive_catalog_plus_group_plus_leaf_payload",
            "tokens",
        ),
        ("ratios", "openai_wrapped_mcp_vs_compact_catalog_payload"),
        ("ratios", "openai_wrapped_mcp_vs_progressive_to_leaf_payload"),
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
    parser = argparse.ArgumentParser(
        description=(
            "Compare end-user request latency for the compact HTTP CLI flow versus "
            "the real MCP SSE tool path."
        )
    )
    parser.add_argument(
        "iterations",
        nargs="?",
        type=int,
        default=DEFAULT_ITERATIONS,
        help=f"Number of iterations per test. Default: {DEFAULT_ITERATIONS}.",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Number of untimed MCP warm-up calls per test. Default: 1.",
    )
    parser.add_argument(
        "--output",
        choices=("pretty", "json"),
        default=DEFAULT_OUTPUT,
        help="Output format.",
    )
    parser.add_argument(
        "--cold-start",
        action="store_true",
        help="Measure a fresh MCP connection per iteration, including initialize and discovery.",
    )
    args = parser.parse_args(argv)

    report = run_latency_benchmark(
        args.iterations,
        verbose=args.output == "pretty",
        warmup=args.warmup,
        cold_start=args.cold_start,
    )
    if args.output == "json":
        print(json.dumps(report, separators=(",", ":"), sort_keys=True))


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
    latency_parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Number of untimed MCP warm-up calls per test. Default: 1.",
    )
    latency_parser.add_argument(
        "--output",
        choices=("pretty", "json"),
        default=DEFAULT_OUTPUT,
        help="Output format.",
    )
    latency_parser.add_argument(
        "--cold-start",
        action="store_true",
        help="Measure a fresh MCP connection per iteration, including initialize and discovery.",
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
        latency_args: list[str] = [str(args.iterations)]
        if args.warmup != 1:
            latency_args.extend(["--warmup", str(args.warmup)])
        if args.output != DEFAULT_OUTPUT:
            latency_args.extend(["--output", args.output])
        if args.cold_start:
            latency_args.append("--cold-start")
        main_latency(latency_args)
        return


if __name__ == "__main__":
    main(sys.argv[1:])


