import asyncio
import datetime
import json
import logging
import textwrap
from contextlib import asynccontextmanager
from typing import Any, Annotated, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse, StreamingResponse
from mcp.server.fastmcp import FastMCP

from tmf620_commands import (
    COMMAND_TREE,
    CommandInvocationError,
    _command_identity,
    _tool_name,
    get_catalog_payload,
    get_command_help_payload,
    invoke_command,
)
from tmf620_core import TMF620Client, TMF620Error, load_config


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("tmf620_mcp_server.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("tmf620-mcp")

config: Optional[dict[str, Any]] = None
client: Optional[TMF620Client] = None
mcp_session_manager: Any = None


class ProductOfferingRequest(BaseModel):
    name: str
    description: str
    catalog_id: str


class ProductSpecificationRequest(BaseModel):
    name: str
    description: str
    version: str = "1.0"


class ApiResponse(BaseModel):
    result: Optional[Any] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None


def _now() -> str:
    return datetime.datetime.now().isoformat()


def _get_client() -> TMF620Client:
    global client
    if client is None:
        client = TMF620Client(config=config)
    return client


def _tool_docstring(
    *,
    summary: str,
    description: str,
    parameters: list[dict[str, Any]] | None = None,
) -> str:
    lines = [summary.strip()]
    description = description.strip()
    if description:
        lines.extend(["", description])
    if parameters:
        lines.extend(["", "Parameters:"])
        for parameter in parameters:
            requirement = "Required" if parameter["required"] else "Optional"
            lines.append(
                f"- {parameter['name']} ({requirement}): {parameter['description']}"
            )
    return "\n".join(lines)


def _mcp_parameter_schema(arg_spec: dict[str, Any]) -> dict[str, Any] | None:
    from tmf620_commands import _arg_dest, _arg_required

    dest = _arg_dest(arg_spec)
    if not dest:
        return None

    description = arg_spec.get("help", "")
    if arg_spec.get("action") == "append":
        return {
            "name": dest,
            "annotation": "list[str] | None",
            "required": False,
            "description": description,
        }

    py_type = arg_spec.get("type")
    annotation = "int" if py_type is int else "str"
    required = _arg_required(arg_spec)
    if not required:
        annotation = f"{annotation} | None"

    return {
        "name": dest,
        "annotation": annotation,
        "required": required,
        "description": description,
    }


def _mcp_tool_parameters(node: dict[str, Any]) -> list[dict[str, Any]]:
    from tmf620_commands import _arg_dest

    required_parameters: list[dict[str, Any]] = []
    optional_parameters: list[dict[str, Any]] = []
    body_parameter_added = False

    for arg_spec in node["args"]:
        dest = _arg_dest(arg_spec)
        if dest in {"body_json", "body_file"}:
            if not body_parameter_added:
                required_parameters.append(
                    {
                        "name": "body",
                        "annotation": "dict[str, Any]",
                        "required": True,
                        "description": "JSON request body as a Python object.",
                    }
                )
                body_parameter_added = True
            continue

        parameter = _mcp_parameter_schema(arg_spec)
        if parameter is not None:
            if parameter["required"]:
                required_parameters.append(parameter)
            else:
                optional_parameters.append(parameter)

    return [*required_parameters, *optional_parameters]


def _build_tool_function_source(
    *,
    function_name: str,
    command: str,
    summary: str,
    description: str,
    parameters: list[dict[str, Any]],
) -> str:
    docstring = _tool_docstring(
        summary=summary, description=description, parameters=parameters
    )
    signature_parts: list[str] = []
    body_lines = ["args: dict[str, Any] = {}"]

    for parameter in parameters:
        param_line = (
            f"{parameter['name']}: "
            f"Annotated[{parameter['annotation']}, Field(description={parameter['description']!r})]"
        )
        if not parameter["required"]:
            param_line += " = None"
        signature_parts.append(param_line)

        if parameter["name"] == "body":
            body_lines.append('args["body"] = body')
            continue

        body_lines.append(f"if {parameter['name']} is not None:")
        body_lines.append(f'    args["{parameter["name"]}"] = {parameter["name"]}')

    body_lines.append(
        f"return invoke_command({command!r}, args, config_path=None, output='json')"
    )

    signature = ", ".join(signature_parts)
    if signature:
        signature = f"({signature})"
    else:
        signature = "()"

    indented_body = textwrap.indent("\n".join(body_lines), "    ")
    return (
        f"def {function_name}{signature} -> Any:\n"
        f"    {docstring!r}\n"
        f"{indented_body}\n"
    )


def _register_mcp_tool(
    mcp_server: FastMCP,
    *,
    tool_name: str,
    command: str,
    summary: str,
    description: str,
    parameters: list[dict[str, Any]],
) -> None:
    namespace: dict[str, Any] = {}
    source = _build_tool_function_source(
        function_name=tool_name,
        command=command,
        summary=summary,
        description=description,
        parameters=parameters,
    )
    exec(source, globals(), namespace)
    mcp_server.add_tool(
        namespace[tool_name],
        name=tool_name,
        description=_tool_docstring(
            summary=summary, description=description, parameters=parameters
        ),
        structured_output=False,
    )


def _register_mcp_tools(mcp_server: FastMCP) -> None:
    _register_mcp_tool(
        mcp_server,
        tool_name="tmf620_health",
        command="health",
        summary="Check TMF620 API health",
        description="Check whether the configured TMF620 API is reachable and return a health payload.",
        parameters=[],
    )
    _register_mcp_tool(
        mcp_server,
        tool_name="tmf620_config",
        command="config",
        summary="Show resolved configuration",
        description="Show the resolved configuration used by the CLI, including the TMF620 API base URL.",
        parameters=[],
    )
    def _discover(
        command_path: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Optional command path to inspect, for example ['offering', 'patch']."
                )
            ),
        ] = None,
    ) -> Any:
        """Print the command catalog or inspect one command path."""
        if not command_path:
            return get_catalog_payload()
        payload = get_command_help_payload(" ".join(command_path))
        if payload is None:
            raise TMF620Error(
                f"Unknown command path for discovery: {' '.join(command_path)}"
            )
        return payload

    mcp_server.add_tool(
        _discover,
        name="tmf620_discover",
        description=(
            "Print the command catalog as JSON, or inspect one command path for "
            "detailed arguments and examples."
        ),
        structured_output=False,
    )

    for node in COMMAND_TREE:
        if node["name"] in {"health", "config"}:
            continue
        if node["kind"] == "command":
            command_path = [node["name"]]
            command = _command_identity(command_path)
            help_payload = get_command_help_payload(command)
            _register_mcp_tool(
                mcp_server,
                tool_name=_tool_name(*command_path),
                command=command,
                summary=help_payload["summary"] if help_payload else node["help"],
                description=(
                    help_payload["description"] if help_payload else node["description"]
                ),
                parameters=_mcp_tool_parameters(node),
            )
            continue

        for child in node["commands"]:
            command_path = [node["name"], child["name"]]
            command = _command_identity(command_path)
            help_payload = get_command_help_payload(command)
            _register_mcp_tool(
                mcp_server,
                tool_name=_tool_name(*command_path),
                command=command,
                summary=help_payload["summary"] if help_payload else child["help"],
                description=(
                    help_payload["description"] if help_payload else child["description"]
                ),
                parameters=_mcp_tool_parameters(child),
            )


def _safe_call(fn, *args):
    try:
        return ApiResponse(result=fn(*args), timestamp=_now())
    except TMF620Error as exc:
        logger.error("%s", exc)
        return ApiResponse(error=str(exc), timestamp=_now())


def _json_error(
    status_code: int,
    code: str,
    message: str,
    *,
    retryable: bool | None = None,
    suggestions: list[str] | None = None,
    next_actions: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    if retryable is not None:
        error["retryable"] = retryable
    if suggestions:
        error["suggestions"] = suggestions
    if next_actions:
        error["next_actions"] = next_actions
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "interface": "cli",
            "version": "1.0",
            "error": error,
        },
    )


def _streaming_result_chunks(command: str, args: dict[str, Any], result: Any):
    yield (
        json.dumps(
            {
                "type": "started",
                "command": command,
                "interface": "cli",
                "version": "1.0",
            }
        )
        + "\n"
    )

    if isinstance(result, list):
        for item in result:
            yield json.dumps({"type": "item", "data": item}) + "\n"
        yield (
            json.dumps({"type": "done", "command": command, "total": len(result)})
            + "\n"
        )
        return

    if isinstance(result, dict) and isinstance(result.get("items"), list):
        for item in result["items"]:
            yield json.dumps({"type": "item", "data": item}) + "\n"
        metadata = {key: value for key, value in result.items() if key != "items"}
        yield (
            json.dumps(
                {
                    "type": "done",
                    "command": command,
                    "total": len(result["items"]),
                    **metadata,
                }
            )
            + "\n"
        )
        return

    yield json.dumps({"type": "result", "command": command, "data": result}) + "\n"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global config, client, mcp_session_manager
    config = load_config()
    client = TMF620Client(config=config)
    try:
        client.test_connection()
        logger.info("Successfully connected to TMF620 API")
        if mcp_session_manager is None:
            yield
            return
        async with mcp_session_manager.run():
            yield
    except Exception as exc:
        logger.error("Failed to initialize TMF620 MCP server: %s", exc)
        raise


app = FastAPI(
    title="TMF620 Product Catalog MCP Server",
    description="MCP server for TMF620 Product Catalog Management API queries and operations",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", operation_id="compat_get_health_status", include_in_schema=False)
async def health_check():
    payload = _get_client().health()
    payload["timestamp"] = _now()
    return payload


@app.get("/api/cli", operation_id="cli_catalog", include_in_schema=False)
async def cli_catalog(verbose: bool = False):
    return get_catalog_payload(verbose=verbose)


@app.post("/api/cli", operation_id="cli_dispatch", include_in_schema=False)
async def cli_dispatch(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return _json_error(400, "invalid_json", "Request body must be valid JSON.")

    if not isinstance(payload, dict):
        return _json_error(
            400, "invalid_request", "Request body must be a JSON object."
        )

    command = payload.get("command")
    if not isinstance(command, str) or not command.strip():
        return _json_error(
            400, "invalid_command", "Command must be a non-empty string."
        )

    args = payload.get("args", {})
    if not isinstance(args, dict):
        return _json_error(400, "invalid_arguments", "args must be a JSON object.")

    stream = payload.get("stream", False)
    if not isinstance(stream, bool):
        return _json_error(400, "invalid_request", "stream must be a boolean.")

    normalized_command = command.strip()

    if normalized_command == "help":
        target = args.get("command")
        if target is None:
            return get_catalog_payload()
        if not isinstance(target, str) or not target.strip():
            return _json_error(
                400,
                "invalid_arguments",
                "help args.command must be a non-empty string.",
            )
        help_payload = get_command_help_payload(target.strip())
        if help_payload is None:
            return _json_error(
                404,
                "help_target_not_found",
                f"Unknown help target: {target}",
                next_actions=[{"type": "help", "request": {"command": "help"}}],
            )
        return help_payload

    try:
        result = await asyncio.to_thread(
            invoke_command,
            normalized_command,
            args,
            config_path=None,
            output="json",
        )
    except CommandInvocationError as exc:
        status_code = 404 if exc.code in {"command_not_found"} else 400
        next_actions: list[dict[str, Any]] | None = None
        if exc.code == "command_not_found":
            next_actions = [{"type": "help", "request": {"command": "help"}}]
        elif exc.code in {"missing_required_argument", "invalid_argument"}:
            next_actions = [
                {
                    "type": "help",
                    "request": {
                        "command": "help",
                        "args": {"command": normalized_command},
                    },
                }
            ]
        return _json_error(status_code, exc.code, str(exc), next_actions=next_actions)
    except TMF620Error as exc:
        return _json_error(500, "tool_invocation_failed", str(exc))
    except TypeError as exc:
        return _json_error(400, "invalid_arguments", str(exc))
    except Exception as exc:
        logger.exception("Unexpected CLI API failure")
        return _json_error(500, "tool_invocation_failed", str(exc))

    if stream:
        return StreamingResponse(
            _streaming_result_chunks(normalized_command, args, result),
            media_type="application/x-ndjson",
        )

    return {
        "status": "ok",
        "interface": "cli",
        "version": "1.0",
        "command": normalized_command,
        "result": result,
    }


@app.get("/catalogs", operation_id="list_catalogs", include_in_schema=False)
async def list_catalogs_endpoint():
    return await asyncio.to_thread(_safe_call, _get_client().list_catalogs)


@app.get("/catalogs/{catalog_id}", operation_id="get_catalog", include_in_schema=False)
async def get_catalog_endpoint(catalog_id: str):
    return await asyncio.to_thread(_safe_call, _get_client().get_catalog, catalog_id)


@app.get(
    "/product-offerings", operation_id="list_product_offerings", include_in_schema=False
)
async def list_product_offerings_endpoint(catalog_id: Optional[str] = None):
    return await asyncio.to_thread(
        _safe_call, _get_client().list_product_offerings, catalog_id
    )


@app.get(
    "/product-offerings/{offering_id}",
    operation_id="get_product_offering",
    include_in_schema=False,
)
async def get_product_offering_endpoint(offering_id: str):
    return await asyncio.to_thread(
        _safe_call, _get_client().get_product_offering, offering_id
    )


@app.post(
    "/product-offerings",
    operation_id="create_product_offering",
    include_in_schema=False,
)
async def create_product_offering_endpoint(request: ProductOfferingRequest):
    return await asyncio.to_thread(
        _safe_call,
        _get_client().create_product_offering,
        request.name,
        request.description,
        request.catalog_id,
    )


@app.get(
    "/product-specifications",
    operation_id="list_product_specifications",
    include_in_schema=False,
)
async def list_product_specifications_endpoint():
    return await asyncio.to_thread(
        _safe_call, _get_client().list_product_specifications
    )


@app.get(
    "/product-specifications/{specification_id}",
    operation_id="get_product_specification",
    include_in_schema=False,
)
async def get_product_specification_endpoint(specification_id: str):
    return await asyncio.to_thread(
        _safe_call, _get_client().get_product_specification, specification_id
    )


@app.post(
    "/product-specifications",
    operation_id="create_product_specification",
    include_in_schema=False,
)
async def create_product_specification_endpoint(request: ProductSpecificationRequest):
    return await asyncio.to_thread(
        _safe_call,
        _get_client().create_product_specification,
        request.name,
        request.description,
        request.version,
    )


@app.get(
    "/server-config", operation_id="compat_get_server_config", include_in_schema=False
)
async def server_config():
    resolved_config = _get_client().config
    return {
        "tmf620_api_url": resolved_config["tmf620_api"]["url"],
        "mcp_server_host": resolved_config["mcp_server"]["host"],
        "mcp_server_port": resolved_config["mcp_server"]["port"],
        "server_name": resolved_config["mcp_server"]["name"],
        "timestamp": _now(),
    }


mcp_server = FastMCP(
    name="TMF620 Product Catalog MCP Server",
    instructions=(
        "TMF620 Product Catalog Management tools with explicit per-command schemas."
    ),
    streamable_http_path="/",
)
_register_mcp_tools(mcp_server)
mcp_app = mcp_server.streamable_http_app()
mcp_session_manager = mcp_server._session_manager
app.mount("/mcp", mcp_app)


def main():
    """Main entry point for the TMF620 MCP server."""
    import uvicorn

    resolved_config = load_config() if config is None else config
    host = resolved_config["mcp_server"]["host"]
    port = resolved_config["mcp_server"]["port"]

    print(f"Starting TMF620 MCP server on http://{host}:{port}")
    print(f"TMF620 API URL: {resolved_config['tmf620_api']['url']}")
    print(f"Health check: http://{host}:{port}/health")
    print(f"API Documentation: http://{host}:{port}/docs")

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
