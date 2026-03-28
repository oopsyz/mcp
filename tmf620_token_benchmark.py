from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import tiktoken

from tmf620_commands import COMMAND_TREE, get_catalog_payload, get_command_help_payload


DEFAULT_ENCODING = "cl100k_base"


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
                "tokens": compact_catalog_tokens + compact_group_tokens,
            },
            "progressive_catalog_plus_group_plus_leaf": {
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


def main() -> None:
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
    args = parser.parse_args()

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


if __name__ == "__main__":
    main()
