import asyncio
import datetime
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mcp import FastApiMCP
from pydantic import BaseModel
from starlette.responses import JSONResponse, StreamingResponse

from tmf620_commands import get_catalog_payload, get_command_help_payload, invoke_command
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


def _json_error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"status": "error", "error": {"code": code, "message": message}},
    )


def _streaming_result_chunks(command: str, args: dict[str, Any], result: Any):
    yield json.dumps(
        {
            "status": "ok",
            "type": "started",
            "command": command,
            "args": args,
            "timestamp": _now(),
        }
    ) + "\n"

    if isinstance(result, list):
        for item in result:
            yield json.dumps({"status": "ok", "type": "item", "item": item}) + "\n"
        yield json.dumps(
            {
                "status": "ok",
                "type": "done",
                "total": len(result),
                "result_kind": "items",
            }
        ) + "\n"
        return

    if isinstance(result, dict) and isinstance(result.get("items"), list):
        for item in result["items"]:
            yield json.dumps({"status": "ok", "type": "item", "item": item}) + "\n"
        metadata = {key: value for key, value in result.items() if key != "items"}
        yield json.dumps(
            {
                "status": "ok",
                "type": "done",
                "total": len(result["items"]),
                "result_kind": "items",
                "metadata": metadata,
            }
        ) + "\n"
        return

    yield json.dumps({"status": "ok", "type": "result", "result": result}) + "\n"
    yield json.dumps(
        {
            "status": "ok",
            "type": "done",
            "result_kind": "single",
        }
    ) + "\n"


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


@app.get("/health", operation_id="get_health_status")
async def health_check():
    payload = _get_client().health()
    payload["timestamp"] = _now()
    return payload


@app.get("/api/cli", operation_id="cli_catalog")
async def cli_catalog():
    return get_catalog_payload()


@app.post("/api/cli", operation_id="cli_dispatch")
async def cli_dispatch(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return _json_error(400, "invalid_json", "Request body must be valid JSON.")

    if not isinstance(payload, dict):
        return _json_error(400, "invalid_request", "Request body must be a JSON object.")

    command = payload.get("command")
    if not isinstance(command, str) or not command.strip():
        return _json_error(400, "invalid_command", "Command must be a non-empty string.")

    args = payload.get("args", {})
    if not isinstance(args, dict):
        return _json_error(400, "invalid_arguments", "args must be a JSON object.")

    stream = bool(payload.get("stream", False))
    normalized_command = command.strip()

    if normalized_command == "help":
        target = args.get("command")
        if target is None:
            return get_catalog_payload()
        if not isinstance(target, str) or not target.strip():
            return _json_error(400, "invalid_arguments", "help args.command must be a non-empty string.")
        help_payload = get_command_help_payload(target.strip())
        if help_payload is None:
            return _json_error(404, "command_not_found", f"Unknown command: {target}")
        return help_payload

    try:
        result = await asyncio.to_thread(
            invoke_command,
            normalized_command,
            args,
            config_path=None,
            output="json",
        )
    except TMF620Error as exc:
        message = str(exc)
        status_code = 404 if message.startswith("Unknown command path:") else 500
        code = "command_not_found" if status_code == 404 else "tool_invocation_failed"
        return _json_error(status_code, code, message)
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
        "service": "tmf620",
        "interface": "cli-http",
        "command": normalized_command,
        "args": args,
        "result": result,
    }


@app.get("/catalogs", operation_id="list_catalogs")
async def list_catalogs_endpoint():
    return await asyncio.to_thread(_safe_call, _get_client().list_catalogs)


@app.get("/catalogs/{catalog_id}", operation_id="get_catalog")
async def get_catalog_endpoint(catalog_id: str):
    return await asyncio.to_thread(_safe_call, _get_client().get_catalog, catalog_id)


@app.get("/product-offerings", operation_id="list_product_offerings")
async def list_product_offerings_endpoint(catalog_id: Optional[str] = None):
    return await asyncio.to_thread(
        _safe_call, _get_client().list_product_offerings, catalog_id
    )


@app.get("/product-offerings/{offering_id}", operation_id="get_product_offering")
async def get_product_offering_endpoint(offering_id: str):
    return await asyncio.to_thread(
        _safe_call, _get_client().get_product_offering, offering_id
    )


@app.post("/product-offerings", operation_id="create_product_offering")
async def create_product_offering_endpoint(request: ProductOfferingRequest):
    return await asyncio.to_thread(
        _safe_call,
        _get_client().create_product_offering,
        request.name,
        request.description,
        request.catalog_id,
    )


@app.get("/product-specifications", operation_id="list_product_specifications")
async def list_product_specifications_endpoint():
    return await asyncio.to_thread(_safe_call, _get_client().list_product_specifications)


@app.get(
    "/product-specifications/{specification_id}",
    operation_id="get_product_specification",
)
async def get_product_specification_endpoint(specification_id: str):
    return await asyncio.to_thread(
        _safe_call, _get_client().get_product_specification, specification_id
    )


@app.post("/product-specifications", operation_id="create_product_specification")
async def create_product_specification_endpoint(request: ProductSpecificationRequest):
    return await asyncio.to_thread(
        _safe_call,
        _get_client().create_product_specification,
        request.name,
        request.description,
        request.version,
    )


@app.get("/server-config", operation_id="get_server_config")
async def server_config():
    resolved_config = _get_client().config
    return {
        "tmf620_api_url": resolved_config["tmf620_api"]["url"],
        "mcp_server_host": resolved_config["mcp_server"]["host"],
        "mcp_server_port": resolved_config["mcp_server"]["port"],
        "server_name": resolved_config["mcp_server"]["name"],
        "timestamp": _now(),
    }


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
