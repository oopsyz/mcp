import argparse
import json
import sys
from typing import Any

from tmf620_core import TMF620Client, TMF620Error


class RichHelpFormatter(
    argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter
):
    """Preserve example formatting while showing defaults."""


def _parser_examples(parser: argparse.ArgumentParser) -> list[str]:
    if not parser.epilog:
        return []
    return [
        line.strip()
        for line in parser.epilog.splitlines()
        if line.strip() and not line.strip().endswith(":")
    ]


def _action_schema(action: argparse.Action) -> dict[str, Any]:
    if not action.option_strings and action.dest == "help":
        return {}
    if action.dest == argparse.SUPPRESS:
        return {}

    kind = "option" if action.option_strings else "argument"
    required = bool(getattr(action, "required", False))
    if not action.option_strings and action.nargs not in ("?", "*"):
        required = True

    schema: dict[str, Any] = {
        "kind": kind,
        "name": action.dest,
        "help": action.help,
        "required": required,
    }

    if action.option_strings:
        schema["flags"] = action.option_strings
    if action.metavar is not None:
        schema["metavar"] = action.metavar
    if action.choices is not None:
        schema["choices"] = list(action.choices)
    if action.default not in (None, argparse.SUPPRESS):
        schema["default"] = action.default
    if action.nargs not in (None, 1):
        schema["nargs"] = action.nargs
    return schema


def _parser_schema(parser: argparse.ArgumentParser) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "prog": parser.prog,
        "description": parser.description,
        "examples": _parser_examples(parser),
        "arguments": [],
        "subcommands": {},
    }

    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, subparser in action.choices.items():
                schema["subcommands"][name] = _parser_schema(subparser)
            continue

        action_info = _action_schema(action)
        if action_info:
            schema["arguments"].append(action_info)

    return schema


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tmf620",
        description=(
            "CLI for the TMF620 Product Catalog Management API.\n\n"
            "The CLI talks directly to the configured TMF620 API URL and is "
            "designed to expose its command surface through --help."
        ),
        epilog=(
            "Examples:\n"
            "  tmf620 health\n"
            "  tmf620 config\n"
            "  tmf620 catalog list\n"
            "  tmf620 catalog get cat-001\n"
            "  tmf620 offering list --catalog-id cat-001\n"
            "  tmf620 offering create --name \"Premium Ethernet\" "
            "--description \"Managed enterprise access\" --catalog-id cat-001\n"
            "  tmf620 specification list\n"
            "  tmf620 specification get ps-001"
        ),
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument(
        "--config",
        help=(
            "Path to config.json. If omitted, uses TMF620_CONFIG_PATH or "
            "./config.json."
        ),
    )
    parser.add_argument(
        "--output",
        choices=["json", "pretty"],
        default="pretty",
        help="Output format for command results.",
    )

    subparsers = parser.add_subparsers(
        dest="resource",
        required=True,
        metavar="COMMAND",
        help=(
            "Top-level command. Run 'tmf620 COMMAND --help' for subcommands "
            "and argument details."
        ),
    )

    health_parser = subparsers.add_parser(
        "health",
        help="Check TMF620 API health",
        description=(
            "Check whether the configured TMF620 API is reachable and return a "
            "health payload."
        ),
        epilog="Example:\n  tmf620 health",
        formatter_class=RichHelpFormatter,
    )
    health_parser.set_defaults(handler=_handle_health)

    config_parser = subparsers.add_parser(
        "config",
        help="Show resolved configuration",
        description=(
            "Show the fully resolved configuration used by the CLI, including "
            "the TMF620 API base URL."
        ),
        epilog="Example:\n  tmf620 config",
        formatter_class=RichHelpFormatter,
    )
    config_parser.set_defaults(handler=_handle_config)

    discover_parser = subparsers.add_parser(
        "discover",
        help="Print command schema for agent discovery",
        description=(
            "Print the CLI command tree, arguments, and examples as structured "
            "JSON for agent/tool discovery."
        ),
        epilog="Example:\n  tmf620 discover",
        formatter_class=RichHelpFormatter,
    )
    discover_parser.set_defaults(handler=_handle_discover)

    catalog_parser = subparsers.add_parser(
        "catalog",
        help="Catalog operations",
        description="List catalogs or retrieve a specific catalog by ID.",
        epilog=(
            "Examples:\n"
            "  tmf620 catalog list\n"
            "  tmf620 catalog get cat-001"
        ),
        formatter_class=RichHelpFormatter,
    )
    catalog_subparsers = catalog_parser.add_subparsers(
        dest="action",
        required=True,
        metavar="ACTION",
        help="Catalog action to run.",
    )

    catalog_list = catalog_subparsers.add_parser(
        "list",
        help="List catalogs",
        description="Return all product catalogs from the configured TMF620 API.",
        epilog="Example:\n  tmf620 catalog list",
        formatter_class=RichHelpFormatter,
    )
    catalog_list.set_defaults(handler=_handle_catalog_list)

    catalog_get = catalog_subparsers.add_parser(
        "get",
        help="Get a catalog by ID",
        description="Return one product catalog by its catalog ID.",
        epilog="Example:\n  tmf620 catalog get cat-001",
        formatter_class=RichHelpFormatter,
    )
    catalog_get.add_argument(
        "catalog_id",
        help="Catalog identifier, for example 'cat-001'.",
    )
    catalog_get.set_defaults(handler=_handle_catalog_get)

    offering_parser = subparsers.add_parser(
        "offering",
        help="Product offering operations",
        description="List, retrieve, or create product offerings.",
        epilog=(
            "Examples:\n"
            "  tmf620 offering list\n"
            "  tmf620 offering list --catalog-id cat-001\n"
            "  tmf620 offering get po-001\n"
            "  tmf620 offering create --name \"Premium Ethernet\" "
            "--description \"Managed enterprise access\" --catalog-id cat-001"
        ),
        formatter_class=RichHelpFormatter,
    )
    offering_subparsers = offering_parser.add_subparsers(
        dest="action",
        required=True,
        metavar="ACTION",
        help="Offering action to run.",
    )

    offering_list = offering_subparsers.add_parser(
        "list",
        help="List offerings",
        description=(
            "Return product offerings. Optionally filter results to a single "
            "catalog."
        ),
        epilog=(
            "Examples:\n"
            "  tmf620 offering list\n"
            "  tmf620 offering list --catalog-id cat-001"
        ),
        formatter_class=RichHelpFormatter,
    )
    offering_list.add_argument(
        "--catalog-id",
        help="Optional catalog identifier used to filter offerings.",
    )
    offering_list.set_defaults(handler=_handle_offering_list)

    offering_get = offering_subparsers.add_parser(
        "get",
        help="Get an offering by ID",
        description="Return one product offering by its offering ID.",
        epilog="Example:\n  tmf620 offering get po-001",
        formatter_class=RichHelpFormatter,
    )
    offering_get.add_argument(
        "offering_id",
        help="Product offering identifier, for example 'po-001'.",
    )
    offering_get.set_defaults(handler=_handle_offering_get)

    offering_create = offering_subparsers.add_parser(
        "create",
        help="Create a product offering",
        description="Create a new product offering in the target catalog.",
        epilog=(
            "Example:\n"
            "  tmf620 offering create --name \"Premium Ethernet\" "
            "--description \"Managed enterprise access\" --catalog-id cat-001"
        ),
        formatter_class=RichHelpFormatter,
    )
    offering_create.add_argument(
        "--name",
        required=True,
        help="Product offering name.",
    )
    offering_create.add_argument(
        "--description",
        required=True,
        help="Product offering description.",
    )
    offering_create.add_argument(
        "--catalog-id",
        required=True,
        help="Catalog identifier that will own the new offering.",
    )
    offering_create.set_defaults(handler=_handle_offering_create)

    specification_parser = subparsers.add_parser(
        "specification",
        help="Product specification operations",
        description="List, retrieve, or create product specifications.",
        epilog=(
            "Examples:\n"
            "  tmf620 specification list\n"
            "  tmf620 specification get ps-001\n"
            "  tmf620 specification create --name \"Broadband Gold\" "
            "--description \"Gold tier broadband spec\" --version 2.0"
        ),
        formatter_class=RichHelpFormatter,
    )
    specification_subparsers = specification_parser.add_subparsers(
        dest="action",
        required=True,
        metavar="ACTION",
        help="Specification action to run.",
    )

    specification_list = specification_subparsers.add_parser(
        "list",
        help="List specifications",
        description="Return all product specifications from the TMF620 API.",
        epilog="Example:\n  tmf620 specification list",
        formatter_class=RichHelpFormatter,
    )
    specification_list.set_defaults(handler=_handle_specification_list)

    specification_get = specification_subparsers.add_parser(
        "get",
        help="Get a specification by ID",
        description="Return one product specification by its specification ID.",
        epilog="Example:\n  tmf620 specification get ps-001",
        formatter_class=RichHelpFormatter,
    )
    specification_get.add_argument(
        "specification_id",
        help="Product specification identifier, for example 'ps-001'.",
    )
    specification_get.set_defaults(handler=_handle_specification_get)

    specification_create = specification_subparsers.add_parser(
        "create",
        help="Create a product specification",
        description="Create a new product specification.",
        epilog=(
            "Example:\n"
            "  tmf620 specification create --name \"Broadband Gold\" "
            "--description \"Gold tier broadband spec\" --version 2.0"
        ),
        formatter_class=RichHelpFormatter,
    )
    specification_create.add_argument(
        "--name",
        required=True,
        help="Specification name.",
    )
    specification_create.add_argument(
        "--description",
        required=True,
        help="Specification description.",
    )
    specification_create.add_argument(
        "--version",
        default="1.0",
        help="Specification version string.",
    )
    specification_create.set_defaults(handler=_handle_specification_create)

    return parser


def _dump(payload: Any, output_format: str) -> None:
    indent = 2 if output_format == "pretty" else None
    print(json.dumps(payload, indent=indent, default=str))


def _client(args: argparse.Namespace) -> TMF620Client:
    return TMF620Client(config_path=args.config)


def _handle_health(args: argparse.Namespace) -> Any:
    return _client(args).health()


def _handle_config(args: argparse.Namespace) -> Any:
    return _client(args).config


def _handle_discover(args: argparse.Namespace) -> Any:
    return _parser_schema(_build_parser())


def _handle_catalog_list(args: argparse.Namespace) -> Any:
    return _client(args).list_catalogs()


def _handle_catalog_get(args: argparse.Namespace) -> Any:
    return _client(args).get_catalog(args.catalog_id)


def _handle_offering_list(args: argparse.Namespace) -> Any:
    return _client(args).list_product_offerings(args.catalog_id)


def _handle_offering_get(args: argparse.Namespace) -> Any:
    return _client(args).get_product_offering(args.offering_id)


def _handle_offering_create(args: argparse.Namespace) -> Any:
    return _client(args).create_product_offering(
        args.name, args.description, args.catalog_id
    )


def _handle_specification_list(args: argparse.Namespace) -> Any:
    return _client(args).list_product_specifications()


def _handle_specification_get(args: argparse.Namespace) -> Any:
    return _client(args).get_product_specification(args.specification_id)


def _handle_specification_create(args: argparse.Namespace) -> Any:
    return _client(args).create_product_specification(
        args.name, args.description, args.version
    )


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        payload = args.handler(args)
    except TMF620Error as exc:
        print(str(exc), file=sys.stderr)
        return 1

    _dump(payload, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
