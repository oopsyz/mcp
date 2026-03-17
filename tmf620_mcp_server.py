import asyncio
import datetime
import logging
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mcp import FastApiMCP
from pydantic import BaseModel

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
