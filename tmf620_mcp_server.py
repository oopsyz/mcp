import asyncio
import datetime
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mcp import FastApiMCP
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse, StreamingResponse

from tmf620_commands import (
    COMMAND_TREE,
    CommandInvocationError,
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


class CliRequest(BaseModel):
    command: str
    args: dict[str, Any] = {}
    stream: bool = False


class CommandArgsRequest(BaseModel):
    args: dict[str, Any] = Field(default_factory=dict)


class DiscoverRequest(BaseModel):
    command_path: list[str] = Field(default_factory=list)


def _now() -> str:
    return datetime.datetime.now().isoformat()


def _get_client() -> TMF620Client:
    global client
    if client is None:
        client = TMF620Client(config=config)
    return client


def _safe_call(fn, *args):
    try:
        return ApiResponse(result=fn(*args), timestamp=_now())
    except TMF620Error as exc:
        logger.error("%s", exc)
        return ApiResponse(error=str(exc), timestamp=_now())


def _command_path_tokens(command_path: list[str]) -> str:
    return " ".join(command_path)


def _command_operation_id(command_path: list[str]) -> str:
    return "tmf620_" + "_".join(token.replace("-", "_") for token in command_path)


def _find_command_node(command_path: list[str]) -> dict[str, Any] | None:
    current_nodes = COMMAND_TREE
    node: dict[str, Any] | None = None

    for token in command_path:
        node = next(
            (candidate for candidate in current_nodes if candidate["name"] == token),
            None,
        )
        if node is None:
            return None
        current_nodes = node.get("commands", [])

    return node


def _validate_command_args(command_path: list[str], args: dict[str, Any]) -> None:
    from tmf620_commands import (
        _find_command_node,
        _arg_dest,
        _arg_required,
        CommandInvocationError,
    )

    node = _find_command_node(command_path)
    if node is None:
        return

    expected: set[str] = set()
    for arg_spec in node["args"]:
        dest = _arg_dest(arg_spec)
        if dest:
            expected.add(dest)
    expected.update({"body", "body_json", "body_file"})

    unexpected = sorted(key for key in args if key not in expected)
    if unexpected:
        raise CommandInvocationError(
            "invalid_argument",
            f"Unknown argument(s): {', '.join(unexpected)}",
        )

    missing: list[str] = []
    for arg_spec in node["args"]:
        dest = _arg_dest(arg_spec)
        if not dest:
            continue
        if _arg_required(arg_spec) and args.get(dest) in (None, ""):
            missing.append(dest)

    if missing:
        raise CommandInvocationError(
            "missing_required_argument",
            f"Missing required arguments: {', '.join(missing)}",
        )


def _register_command_route(
    *,
    command_path: list[str],
    summary: str,
    description: str,
    handler,
) -> None:
    operation_id = _command_operation_id(command_path)
    route_path = "/commands/" + "/".join(command_path)

    async def endpoint(request: CommandArgsRequest):
        try:
            _validate_command_args(command_path, request.args)
            return await asyncio.to_thread(handler, request.args)
        except CommandInvocationError as exc:
            status_code = 404 if exc.code == "command_not_found" else 400
            next_actions = None
            if exc.code in {"missing_required_argument", "invalid_argument"}:
                next_actions = [
                    {
                        "type": "help",
                        "request": {
                            "command": "help",
                            "args": {"command": _command_path_tokens(command_path)},
                        },
                    }
                ]
            return _json_error(
                status_code,
                exc.code,
                str(exc),
                next_actions=next_actions,
            )
        except TMF620Error as exc:
            return _json_error(500, "tool_invocation_failed", str(exc))
        except TypeError as exc:
            return _json_error(400, "invalid_arguments", str(exc))
        except Exception as exc:
            logger.exception("Unexpected command route failure")
            return _json_error(500, "tool_invocation_failed", str(exc))

    endpoint.__name__ = operation_id
    app.add_api_route(
        route_path,
        endpoint,
        methods=["POST"],
        operation_id=operation_id,
        summary=summary,
        description=description,
    )


def _register_mcp_command_routes() -> None:
    _register_command_route(
        command_path=["health"],
        summary="Check TMF620 API health",
        description=(
            "Check whether the configured TMF620 API is reachable and return a health payload."
        ),
        handler=lambda _args: _get_client().health(),
    )
    _register_command_route(
        command_path=["config"],
        summary="Show resolved configuration",
        description=(
            "Show the resolved configuration used by the CLI, including the TMF620 API base URL."
        ),
        handler=lambda _args: _get_client().config,
    )

    def _discover_handler(args: dict[str, Any]) -> Any:
        command_path = args.get("command_path", [])
        if not command_path:
            return get_catalog_payload()
        if not isinstance(command_path, list) or not all(
            isinstance(token, str) and token.strip() for token in command_path
        ):
            raise TMF620Error("command_path must be a list of non-empty strings.")
        payload = get_command_help_payload(" ".join(command_path))
        if payload is None:
            raise TMF620Error(
                f"Unknown command path for discovery: {' '.join(command_path)}"
            )
        return payload

    async def discover_endpoint(request: DiscoverRequest):
        try:
            return await asyncio.to_thread(
                _discover_handler, {"command_path": request.command_path}
            )
        except TMF620Error as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    discover_endpoint.__name__ = "tmf620_discover"
    app.add_api_route(
        "/commands/discover",
        discover_endpoint,
        methods=["POST"],
        operation_id="tmf620_discover",
        summary="Print command catalog or per-command schema",
        description=(
            "Print the command catalog as JSON, or inspect one command path for detailed arguments and examples."
        ),
    )

    for node in COMMAND_TREE:
        if node["name"] in {"health", "config"}:
            continue
        if node["kind"] == "command":
            command_path = [node["name"]]
            command = _command_path_tokens(command_path)
            _register_command_route(
                command_path=command_path,
                summary=node["help"],
                description=node["description"],
                handler=lambda _args, command=command: invoke_command(
                    command,
                    {},
                    config_path=None,
                    output="json",
                ),
            )
            continue

        for child in node["commands"]:
            command_path = [node["name"], child["name"]]
            command = _command_path_tokens(command_path)

            def _handler_factory(command: str):
                def _handler(args: dict[str, Any]) -> Any:
                    return invoke_command(
                        command,
                        args,
                        config_path=None,
                        output="json",
                    )

                return _handler

            _register_command_route(
                command_path=command_path,
                summary=child["help"],
                description=child["description"],
                handler=_handler_factory(command),
            )


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
    global config, client
    config = load_config()
    client = TMF620Client(config=config)
    try:
        client.test_connection()
        logger.info("Successfully connected to TMF620 API")
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


_register_mcp_command_routes()

mcp = FastApiMCP(app)
mcp.mount()


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
