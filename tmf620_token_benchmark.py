from __future__ import annotations

import argparse
import json
from typing import Any

import tiktoken

from tmf620_commands import get_catalog_payload, get_command_help_payload
from tmf620_mcp_server import mcp


DEFAULT_ENCODING = "cl100k_base"


def _dump(payload: Any) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _token_count(encoding_name: str, payload: Any) -> tuple[int, int]:
    encoded = tiktoken.get_encoding(encoding_name).encode(_dump(payload))
    return len(_dump(payload)), len(encoded)


def build_report(encoding_name: str = DEFAULT_ENCODING) -> dict[str, Any]:
    raw_tools = [tool.model_dump(mode="json", exclude_none=True) for tool in mcp.tools]
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
    args = parser.parse_args()

    report = build_report(args.encoding)
    if args.output == "json":
        print(json.dumps(report, separators=(",", ":"), sort_keys=True))
        return

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
