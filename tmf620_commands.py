import argparse
import json
from pathlib import Path
from typing import Any, Callable

from tmf620_core import TMF620Client, TMF620Error


Handler = Callable[[argparse.Namespace], Any]

SERVICE_ID = "tmf620"
SERVICE_NAMESPACE = "tmf620/catalogmgt"
CANONICAL_CLI_ENDPOINT = f"/cli/{SERVICE_NAMESPACE}"


class CommandInvocationError(TMF620Error):
    """CLI-facing invocation error with a machine-readable code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class RichHelpFormatter(
    argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter
):
    """Preserve example formatting while showing defaults."""


RESOURCE_SPECS = [
    {
        "command": "category",
        "resource_name": "category",
        "id_arg": "category_id",
        "id_help": "Category identifier, for example 'category-001'.",
        "summary": "Category operations",
        "description": "List, retrieve, create, patch, or delete categories.",
        "list_examples": [
            "category list",
            "category list --limit 5",
            "category list --filter name=Internet",
        ],
    },
    {
        "command": "catalog",
        "resource_name": "product_catalog",
        "id_arg": "catalog_id",
        "id_help": "Catalog identifier, for example 'catalog-001'.",
        "summary": "Product catalog operations",
        "description": "List, retrieve, create, patch, or delete product catalogs.",
        "list_examples": [
            "catalog list",
            "catalog list --lifecycle-status Active --limit 5",
        ],
        "supports_lifecycle": True,
    },
    {
        "command": "offering",
        "resource_name": "product_offering",
        "id_arg": "offering_id",
        "id_help": "Product offering identifier, for example 'po-001'.",
        "summary": "Product offering operations",
        "description": "List, retrieve, create, patch, or delete product offerings.",
        "list_examples": [
            "offering list",
            "offering list --catalog-id cat-001 --limit 10",
            "offering list --lifecycle-status Active",
        ],
        "supports_lifecycle": True,
        "supports_catalog_filter": True,
    },
    {
        "command": "price",
        "resource_name": "product_offering_price",
        "id_arg": "price_id",
        "id_help": "Product offering price identifier, for example 'pop-001'.",
        "summary": "Product offering price operations",
        "description": "List, retrieve, create, patch, or delete product offering prices.",
        "list_examples": [
            "price list",
            "price list --limit 10",
        ],
        "supports_lifecycle": True,
    },
    {
        "command": "specification",
        "resource_name": "product_specification",
        "id_arg": "specification_id",
        "id_help": "Product specification identifier, for example 'ps-001'.",
        "summary": "Product specification operations",
        "description": "List, retrieve, create, patch, or delete product specifications.",
        "list_examples": [
            "specification list",
            "specification list --lifecycle-status Active --limit 5",
        ],
        "supports_lifecycle": True,
    },
    {
        "command": "import-job",
        "resource_name": "import_job",
        "id_arg": "import_job_id",
        "id_help": "Import job identifier, for example 'import-001'.",
        "summary": "Import job operations",
        "description": "List, retrieve, create, or delete import jobs.",
        "list_examples": [
            "import-job list",
            "import-job get import-001",
        ],
        "actions": ("list", "get", "create", "delete"),
    },
    {
        "command": "export-job",
        "resource_name": "export_job",
        "id_arg": "export_job_id",
        "id_help": "Export job identifier, for example 'export-001'.",
        "summary": "Export job operations",
        "description": "List, retrieve, create, or delete export jobs.",
        "list_examples": [
            "export-job list",
            "export-job get export-001",
        ],
        "actions": ("list", "get", "create", "delete"),
    },
]


GLOBAL_OPTIONS: list[dict[str, Any]] = [
    {
        "flags": ["--config"],
        "help": (
            "Path to config.json. If omitted, uses TMF620_CONFIG_PATH or ./config.json."
        ),
    },
    {
        "flags": ["--output"],
        "choices": ["json", "pretty"],
        "default": "pretty",
        "help": "Output format for command results.",
    },
]


def _main_examples() -> list[str]:
    return [
        "health",
        "config",
        "catalog list --lifecycle-status Active --limit 5",
        "offering list --catalog-id cat-001 --limit 10",
        "price get pop-001",
        "specification create --body-file specification.json",
        "hub create --body-file hub.json",
    ]


def _client(args: argparse.Namespace) -> TMF620Client:
    return TMF620Client(config_path=args.config)


def _arg_dest(arg_spec: dict[str, Any]) -> str | None:
    dest = arg_spec.get("dest")
    if dest:
        return dest
    if "name" in arg_spec:
        return arg_spec["name"]
    if "flags" in arg_spec:
        return arg_spec["flags"][-1].lstrip("-").replace("-", "_")
    return None


def _arg_required(arg_spec: dict[str, Any]) -> bool:
    if "required" in arg_spec:
        return bool(arg_spec["required"])
    return "name" in arg_spec


def _parse_filters(raw_filters: list[str] | None) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for item in raw_filters or []:
        if "=" not in item:
            raise TMF620Error(
                f"Invalid filter '{item}'. Expected KEY=VALUE, for example --filter name=Internet."
            )
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise TMF620Error(f"Invalid filter '{item}'. Filter key cannot be empty.")
        parsed[key] = value
    return parsed


def _load_payload(args: argparse.Namespace) -> dict[str, Any]:
    body_json = getattr(args, "body_json", None)
    body_file = getattr(args, "body_file", None)
    raw_payload: str

    if body_json:
        raw_payload = body_json
    elif body_file:
        raw_payload = Path(body_file).read_text(encoding="utf-8")
    else:
        raise TMF620Error("A JSON payload is required. Use --body-json or --body-file.")

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise TMF620Error(f"Invalid JSON payload: {exc}") from exc

    if not isinstance(payload, dict):
        raise TMF620Error("Payload must be a JSON object.")
    return payload


def _handle_health(args: argparse.Namespace) -> Any:
    return _client(args).health()


def _handle_config(args: argparse.Namespace) -> Any:
    return _client(args).config


def _handle_resource_list(args: argparse.Namespace) -> Any:
    filters = _parse_filters(getattr(args, "filters", None))
    lifecycle_status = getattr(args, "lifecycle_status", None)
    if lifecycle_status:
        filters["lifecycleStatus"] = lifecycle_status

    catalog_id = getattr(args, "catalog_id", None)
    if catalog_id:
        filters["catalog.id"] = catalog_id

    return _client(args).list_resource(
        args.resource_name,
        fields=args.fields,
        limit=args.limit,
        offset=args.offset,
        filters=filters,
    )


def _handle_resource_get(args: argparse.Namespace) -> Any:
    return _client(args).get_resource(
        args.resource_name,
        getattr(args, args.resource_id_arg),
        fields=args.fields,
    )


def _handle_resource_create(args: argparse.Namespace) -> Any:
    return _client(args).create_resource(
        args.resource_name,
        _load_payload(args),
        fields=args.fields,
    )


def _handle_resource_patch(args: argparse.Namespace) -> Any:
    return _client(args).patch_resource(
        args.resource_name,
        getattr(args, args.resource_id_arg),
        _load_payload(args),
        fields=args.fields,
    )


def _handle_resource_delete(args: argparse.Namespace) -> Any:
    return _client(args).delete_resource(
        args.resource_name,
        getattr(args, args.resource_id_arg),
    )


def _handle_hub_create(args: argparse.Namespace) -> Any:
    return _client(args).create_hub(_load_payload(args))


def _handle_hub_delete(args: argparse.Namespace) -> Any:
    return _client(args).delete_hub(args.hub_id)


def _command(
    name: str,
    help_text: str,
    description: str,
    examples: list[str],
    handler: Handler,
    args: list[dict[str, Any]] | None = None,
    defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "kind": "command",
        "help": help_text,
        "description": description,
        "examples": examples,
        "args": args or [],
        "handler": handler,
        "defaults": defaults or {},
    }


def _group(
    name: str,
    help_text: str,
    description: str,
    examples: list[str],
    commands: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "name": name,
        "kind": "group",
        "help": help_text,
        "description": description,
        "examples": examples,
        "commands": commands,
    }


def _list_args(resource_spec: dict[str, Any]) -> list[dict[str, Any]]:
    args = [
        {
            "flags": ["--fields"],
            "help": "Comma-separated first-level fields to return.",
        },
        {
            "flags": ["--limit"],
            "type": int,
            "help": "Maximum number of records to return.",
        },
        {
            "flags": ["--offset"],
            "type": int,
            "help": "Number of records to skip before returning results.",
        },
        {
            "flags": ["--filter"],
            "dest": "filters",
            "action": "append",
            "default": [],
            "metavar": "KEY=VALUE",
            "help": "Additional query filters. Repeat for multiple values.",
        },
    ]

    if resource_spec.get("supports_lifecycle"):
        args.append(
            {
                "flags": ["--lifecycle-status"],
                "dest": "lifecycle_status",
                "help": "Optional lifecycle status filter.",
            }
        )

    if resource_spec.get("supports_catalog_filter"):
        args.append(
            {
                "flags": ["--catalog-id"],
                "dest": "catalog_id",
                "help": "Optional catalog identifier used as catalog.id filter.",
            }
        )

    return args


def _fields_arg() -> dict[str, Any]:
    return {
        "flags": ["--fields"],
        "help": "Comma-separated first-level fields to return.",
    }


def _payload_args() -> list[dict[str, Any]]:
    return [
        _fields_arg(),
        {
            "flags": ["--body-json"],
            "help": "Inline JSON object payload for create or patch.",
        },
        {
            "flags": ["--body-file"],
            "help": "Path to a JSON file containing the request payload.",
        },
    ]


def _resource_commands(resource_spec: dict[str, Any]) -> list[dict[str, Any]]:
    actions = resource_spec.get(
        "actions", ("list", "get", "create", "patch", "delete")
    )
    commands: list[dict[str, Any]] = []
    defaults = {
        "resource_name": resource_spec["resource_name"],
        "resource_id_arg": resource_spec["id_arg"],
    }

    if "list" in actions:
        commands.append(
            _command(
                "list",
                f"List {resource_spec['command']} resources",
                f"Return {resource_spec['command']} resources from the configured TMF620 API.",
                resource_spec["list_examples"],
                _handle_resource_list,
                args=_list_args(resource_spec),
                defaults=defaults,
            )
        )

    if "get" in actions:
        commands.append(
            _command(
                "get",
                f"Get a {resource_spec['command']} resource by ID",
                f"Return one {resource_spec['command']} resource by ID.",
                [
                    f"tmf620 {resource_spec['command']} get sample-{resource_spec['command']}"
                ],
                _handle_resource_get,
                args=[
                    {
                        "name": resource_spec["id_arg"],
                        "help": resource_spec["id_help"],
                    },
                    _fields_arg(),
                ],
                defaults=defaults,
            )
        )

    if "create" in actions:
        commands.append(
            _command(
                "create",
                f"Create a {resource_spec['command']} resource",
                (
                    f"Create a new {resource_spec['command']} resource. "
                    "Use --body-json or --body-file because the TMF payload is too wide "
                    "for practical shell flags."
                ),
                [
                    f"tmf620 {resource_spec['command']} create --body-file payload.json"
                ],
                _handle_resource_create,
                args=_payload_args(),
                defaults=defaults,
            )
        )

    if "patch" in actions:
        commands.append(
            _command(
                "patch",
                f"Patch a {resource_spec['command']} resource",
                (
                    f"Partially update one {resource_spec['command']} resource by ID. "
                    "Use --body-json or --body-file for the patch payload."
                ),
                [
                    f"tmf620 {resource_spec['command']} patch sample-{resource_spec['command']} --body-file patch.json"
                ],
                _handle_resource_patch,
                args=[
                    {
                        "name": resource_spec["id_arg"],
                        "help": resource_spec["id_help"],
                    },
                    *_payload_args(),
                ],
                defaults=defaults,
            )
        )

    if "delete" in actions:
        commands.append(
            _command(
                "delete",
                f"Delete a {resource_spec['command']} resource",
                f"Delete one {resource_spec['command']} resource by ID.",
                [
                    f"tmf620 {resource_spec['command']} delete sample-{resource_spec['command']}"
                ],
                _handle_resource_delete,
                args=[
                    {
                        "name": resource_spec["id_arg"],
                        "help": resource_spec["id_help"],
                    }
                ],
                defaults=defaults,
            )
        )

    return commands


def _command_tree() -> list[dict[str, Any]]:
    tree: list[dict[str, Any]] = [
        _command(
            "health",
            "Check TMF620 API health",
            "Check whether the configured TMF620 API is reachable and return a health payload.",
            ["tmf620 health"],
            _handle_health,
        ),
        _command(
            "config",
            "Show resolved configuration",
            "Show the resolved configuration used by the CLI, including the TMF620 API base URL.",
            ["tmf620 config"],
            _handle_config,
        ),
    ]

    for resource_spec in RESOURCE_SPECS:
        tree.append(
            _group(
                resource_spec["command"],
                resource_spec["summary"],
                resource_spec["description"],
                resource_spec["list_examples"],
                _resource_commands(resource_spec),
            )
        )

    tree.append(
        _group(
            "hub",
            "Event hub subscription operations",
            "Create or delete TMF620 event hub subscriptions.",
            [
                "tmf620 hub create --body-file hub.json",
                "tmf620 hub delete hub-001",
            ],
            [
                _command(
                    "create",
                    "Create an event hub subscription",
                    "Create a TMF620 event subscription hub from a JSON payload.",
                    ["tmf620 hub create --body-file hub.json"],
                    _handle_hub_create,
                    args=[
                        {
                            "flags": ["--body-json"],
                            "help": "Inline JSON object payload for the hub subscription.",
                        },
                        {
                            "flags": ["--body-file"],
                            "help": "Path to a JSON file containing the hub subscription payload.",
                        },
                    ],
                ),
                _command(
                    "delete",
                    "Delete an event hub subscription",
                    "Delete an existing TMF620 event subscription hub by ID.",
                    ["tmf620 hub delete hub-001"],
                    _handle_hub_delete,
                    args=[
                        {
                            "name": "hub_id",
                            "help": "Hub identifier, for example 'hub-001'.",
                        }
                    ],
                ),
            ],
        )
    )

    return tree


COMMAND_TREE = _command_tree()


def _split_command_path(command: str) -> list[str]:
    return [token for token in command.split() if token]


def _find_command_node(path: list[str]) -> dict[str, Any] | None:
    current_nodes = COMMAND_TREE
    node: dict[str, Any] | None = None
    for token in path:
        node = next(
            (candidate for candidate in current_nodes if candidate["name"] == token),
            None,
        )
        if node is None:
            return None
        current_nodes = node.get("commands", [])
    if node is None or node["kind"] != "command":
        return None
    return node


def _action_type(action: argparse.Action) -> str:
    if isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
        return "boolean"
    if action.type is int:
        return "integer"
    if action.type is float:
        return "number"
    if action.type is str or action.type is None:
        return "string"
    if hasattr(action.type, "__name__"):
        return str(action.type.__name__)
    return "string"


def _action_schema(action: argparse.Action) -> dict[str, Any]:
    if action.dest == "help" or action.dest == argparse.SUPPRESS:
        return {}

    required = bool(getattr(action, "required", False))
    if not action.option_strings and action.nargs not in ("?", "*"):
        required = True

    schema: dict[str, Any] = {
        "name": action.dest,
        "type": _action_type(action),
        "required": required,
        "default": None,
    }

    if action.default not in (None, argparse.SUPPRESS):
        schema["default"] = action.default
    if action.help not in (None, argparse.SUPPRESS):
        schema["description"] = action.help
    if action.choices is not None:
        schema["enum"] = list(action.choices)
    return schema


def _parser_examples(parser: argparse.ArgumentParser) -> list[str]:
    if not parser.epilog:
        return []
    return [
        line.strip()
        for line in parser.epilog.splitlines()
        if line.strip() and not line.strip().endswith(":")
    ]


def _example_request_args(arguments: list[dict[str, Any]]) -> dict[str, Any]:
    args: dict[str, Any] = {}
    for argument in arguments:
        if argument["required"]:
            args[argument["name"]] = f"<{argument['name']}>"
        elif argument["default"] not in (None, [], ""):
            args[argument["name"]] = argument["default"]
    return args


def _parser_schema(parser: argparse.ArgumentParser) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "summary": (parser.description or "").splitlines()[0] if parser.description else "",
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


def _command_identity(path: list[str]) -> str:
    return " ".join(path)


def _tool_name(*segments: str) -> str:
    return "tmf620_" + "_".join(segment.replace("-", "_") for segment in segments)


def _catalog_entries() -> list[dict[str, Any]]:
    commands: list[dict[str, Any]] = []
    for node in COMMAND_TREE:
        commands.append(
            {
                "name": node["name"],
                "kind": node["kind"],
                "summary": node["help"],
            }
        )
    return commands


def _catalog_payload(
    parser: argparse.ArgumentParser, *, verbose: bool = False
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "ok",
        "interface": "cli",
        "version": "1.0",
        "service": SERVICE_ID,
        "namespace": SERVICE_NAMESPACE,
        "canonical_endpoint": CANONICAL_CLI_ENDPOINT,
        "how_to_invoke": {
            "endpoint": f"POST {CANONICAL_CLI_ENDPOINT}",
            "shape": {"command": "<command_name>", "args": {}, "stream": False},
        },
        "how_to_get_help": {
            "all_commands": (
                f'GET {CANONICAL_CLI_ENDPOINT} or '
                f'POST {CANONICAL_CLI_ENDPOINT} {{"command":"help"}}'
            ),
            "one_command": (
                f'POST {CANONICAL_CLI_ENDPOINT} '
                '{"command":"help","args":{"command":"<command path>"}}'
            ),
        },
        "commands": _catalog_entries(),
        "total": len(COMMAND_TREE),
    }
    if verbose:
        payload["description"] = parser.description
        payload["examples"] = _main_examples()
    return payload


def _find_group_node(path: list[str]) -> dict[str, Any] | None:
    current_nodes = COMMAND_TREE
    node: dict[str, Any] | None = None
    for token in path:
        node = next(
            (candidate for candidate in current_nodes if candidate["name"] == token),
            None,
        )
        if node is None:
            return None
        current_nodes = node.get("commands", [])
    if node is None or node["kind"] != "group":
        return None
    return node


def _command_payload(
    parser: argparse.ArgumentParser, path: list[str], *, verbose: bool = False
) -> dict[str, Any] | None:
    node = _find_command_node(path)
    if node is not None:
        schema = _parser_schema(parser)
        current = schema

        for token in path:
            current = current["subcommands"].get(token)
            if current is None:
                return None

        return {
            "status": "ok",
            "interface": "cli",
            "version": "1.0",
            "command": _command_identity(path),
            "summary": node["help"],
            "description": current["description"],
            "arguments": current["arguments"],
            "examples": [
                {
                    "description": f"Invoke {_command_identity(path)}",
                    "request": {
                        "command": _command_identity(path),
                        "args": _example_request_args(current["arguments"]),
                    },
                },
                *[
                    {
                        "description": f"Shell example for {_command_identity(path)}",
                        "request": {
                            "command": _command_identity(path),
                            "args": _example_request_args(current["arguments"]),
                        },
                        "shell": example,
                    }
                    for example in current["examples"]
                ],
            ],
        }

    current_group = _find_group_node(path)
    if current_group is None:
        return None

    return {
        "status": "ok",
        "interface": "cli",
        "version": "1.0",
        "command": _command_identity(path),
        "kind": "group",
        "summary": current_group["help"],
        "description": current_group["description"],
        "subcommands": [
            {
                "name": child["name"],
                "kind": child["kind"],
                "summary": child["help"],
            }
            for child in current_group["commands"]
        ],
    }


def get_catalog_payload(*, verbose: bool = False) -> dict[str, Any]:
    return _catalog_payload(build_parser(), verbose=verbose)


def get_command_help_payload(command: str, *, verbose: bool = False) -> dict[str, Any] | None:
    path = _split_command_path(command)
    if not path:
        return get_catalog_payload(verbose=verbose)
    return _command_payload(build_parser(), path, verbose=verbose)


def invoke_command(
    command: str,
    args: dict[str, Any] | None = None,
    *,
    config_path: str | None = None,
    output: str = "json",
) -> Any:
    path = _split_command_path(command)
    if not path:
        raise CommandInvocationError("invalid_command", "Command cannot be empty.")

    node = _find_command_node(path)
    if node is None:
        raise CommandInvocationError("command_not_found", f"Unknown command: {command}")

    namespace_data: dict[str, Any] = {"config": config_path, "output": output}
    namespace_data.update(node["defaults"])

    for arg_spec in node["args"]:
        dest = _arg_dest(arg_spec)
        if not dest:
            continue

        if dest in {"body_json", "body_file"}:
            namespace_data.setdefault(dest, None)
            continue

        if "default" in arg_spec:
            namespace_data.setdefault(dest, arg_spec["default"])
        elif arg_spec.get("action") == "append":
            namespace_data.setdefault(dest, [])
        else:
            namespace_data.setdefault(dest, None)

    provided_args = dict(args or {})
    body_payload = provided_args.pop("body", None)
    if body_payload is not None:
        namespace_data["body_json"] = json.dumps(body_payload)
    if "body_json" in provided_args:
        namespace_data["body_json"] = provided_args.pop("body_json")
    if "body_file" in provided_args:
        namespace_data["body_file"] = provided_args.pop("body_file")

    expected_args = {"body", "body_json", "body_file"}
    for arg_spec in node["args"]:
        dest = _arg_dest(arg_spec)
        if dest:
            expected_args.add(dest)

    unexpected_args = sorted(key for key in provided_args if key not in expected_args)
    if unexpected_args:
        raise CommandInvocationError(
            "invalid_argument",
            f"Unknown argument(s): {', '.join(unexpected_args)}",
        )

    for key, value in provided_args.items():
        namespace_data[key] = value

    missing_required: list[str] = []
    for arg_spec in node["args"]:
        dest = _arg_dest(arg_spec)
        if not dest:
            continue
        if _arg_required(arg_spec) and namespace_data.get(dest) in (None, ""):
            missing_required.append(dest)

    if missing_required:
        raise CommandInvocationError(
            "missing_required_argument",
            f"Missing required arguments: {', '.join(missing_required)}",
        )

    args_ns = argparse.Namespace(**namespace_data)
    return node["handler"](args_ns)


def _handle_discover(args: argparse.Namespace) -> Any:
    parser = build_parser()
    if not args.command_path:
        return _catalog_payload(parser)

    payload = _command_payload(parser, args.command_path)
    if payload is None:
        raise TMF620Error(
            f"Unknown command path for discovery: {' '.join(args.command_path)}"
        )
    return payload


def _apply_argument(parser: argparse.ArgumentParser, spec: dict[str, Any]) -> None:
    kwargs = {key: value for key, value in spec.items() if key not in {"flags", "name"}}
    if "flags" in spec:
        parser.add_argument(*spec["flags"], **kwargs)
        return
    parser.add_argument(spec["name"], **kwargs)


def _examples_epilog(examples: list[str]) -> str | None:
    if not examples:
        return None
    return "Examples:\n" + "\n".join(f"  {example}" for example in examples)


def _wire_node(
    subparsers: argparse._SubParsersAction,
    node: dict[str, Any],
    parent_path: list[str],
) -> None:
    parser = subparsers.add_parser(
        node["name"],
        help=node["help"],
        description=node["description"],
        epilog=_examples_epilog(node["examples"]),
        formatter_class=RichHelpFormatter,
    )
    path = [*parent_path, node["name"]]

    if node["kind"] == "group":
        child_subparsers = parser.add_subparsers(
            dest=f"{node['name'].replace('-', '_')}_action",
            required=True,
            metavar="ACTION",
            help=f"{node['name'].title()} action to run.",
        )
        for child in node["commands"]:
            _wire_node(child_subparsers, child, path)
        return

    for arg in node["args"]:
        _apply_argument(parser, arg)
    parser.set_defaults(handler=node["handler"], command_path=path, **node["defaults"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tmf620",
        description=(
            "Structured command schema for the TMF620 Product Catalog Management API.\n\n"
            "This parser definition backs the HTTP CLI API discover -> inspect -> invoke flow."
        ),
        epilog=_examples_epilog(_main_examples()),
        formatter_class=RichHelpFormatter,
    )

    for option in GLOBAL_OPTIONS:
        _apply_argument(parser, option)

    subparsers = parser.add_subparsers(
        dest="resource",
        required=True,
        metavar="COMMAND",
        help="Top-level command. Use GET /cli/tmf620/catalogmgt for the command catalog.",
    )

    discover_parser = subparsers.add_parser(
        "discover",
        help="Print command catalog or per-command schema",
        description=(
            "Print the command catalog as JSON, or inspect one command path "
            "for detailed arguments and examples."
        ),
        epilog=_examples_epilog(
            [
                "discover",
                "discover offering patch",
                "discover import-job create",
            ]
        ),
        formatter_class=RichHelpFormatter,
    )
    discover_parser.add_argument(
        "command_path",
        nargs="*",
        help="Optional command path to inspect, for example: offering patch",
    )
    discover_parser.set_defaults(handler=_handle_discover, command_path=[])

    for node in COMMAND_TREE:
        _wire_node(subparsers, node, [])

    return parser


def dump_payload(payload: Any, output_format: str) -> None:
    indent = 2 if output_format == "pretty" else None
    print(json.dumps(payload, indent=indent, default=str))


