#!/usr/bin/env python3
"""
TMF637 Product Inventory API MCP Server
Exposes TMF637 Product Inventory API operations as MCP tools for AI agents
"""

import os
import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Query, Body, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mcp import FastApiMCP
import uvicorn

# Import the TMF637 client
from tmf637_client import TMF637Client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tmf637-mcp-server")

# Initialize FastAPI app
app = FastAPI(
    title="TMF637 Product Inventory API MCP Server",
    description="MCP server for TMF637 Product Inventory API",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize TMF637 client
tmf637_client = TMF637Client(os.getenv("TMF637_API_URL", "http://localhost:8637"))

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    await tmf637_client.close()

# Define FastAPI endpoints with operation_ids that will become MCP tool names

@app.get("/api/products", tags=["product"], operation_id="tmf637_list_products")
async def api_list_products(
    fields: Optional[str] = Query(None, description="Fields to include in the response"),
    offset: Optional[int] = Query(None, description="Pagination offset"),
    limit: Optional[int] = Query(None, description="Pagination limit")
):
    """List Product objects with optional filtering and pagination"""
    try:
        result = await tmf637_client.list_products(
            fields=fields,
            offset=offset,
            limit=limit
        )
        return result
    except Exception as e:
        logger.error(f"Failed to list products: {e}")
        raise

@app.post("/api/products", tags=["product"], operation_id="tmf637_create_product")
async def api_create_product(
    product: Dict[str, Any] = Body(..., description="Product data")
):
    """Create a new Product"""
    try:
        result = await tmf637_client.create_product(product)
        return result
    except Exception as e:
        logger.error(f"Failed to create product: {e}")
        raise

@app.get("/api/products/{product_id}", tags=["product"], operation_id="tmf637_get_product")
async def api_get_product(
    product_id: str = Path(..., description="Product ID"),
    fields: Optional[str] = Query(None, description="Fields to include in the response")
):
    """Retrieve a Product by ID"""
    try:
        result = await tmf637_client.get_product(product_id, fields=fields)
        return result
    except Exception as e:
        logger.error(f"Failed to get product: {e}")
        raise

@app.put("/api/products/{product_id}", tags=["product"], operation_id="tmf637_update_product")
async def api_update_product(
    product_id: str = Path(..., description="Product ID"),
    product: Dict[str, Any] = Body(..., description="Updated product data")
):
    """Update a Product"""
    try:
        result = await tmf637_client.update_product(product_id, product)
        return result
    except Exception as e:
        logger.error(f"Failed to update product: {e}")
        raise

@app.patch("/api/products/{product_id}", tags=["product"], operation_id="tmf637_patch_product")
async def api_patch_product(
    product_id: str = Path(..., description="Product ID"),
    patch: Dict[str, Any] = Body(..., description="Patch data")
):
    """Patch a Product"""
    try:
        result = await tmf637_client.patch_product(product_id, patch)
        return result
    except Exception as e:
        logger.error(f"Failed to patch product: {e}")
        raise

@app.delete("/api/products/{product_id}", tags=["product"], operation_id="tmf637_delete_product")
async def api_delete_product(
    product_id: str = Path(..., description="Product ID")
):
    """Delete a Product"""
    try:
        result = await tmf637_client.delete_product(product_id)
        return result
    except Exception as e:
        logger.error(f"Failed to delete product: {e}")
        raise

@app.post("/api/hub", tags=["hub"], operation_id="tmf637_create_hub")
async def api_create_hub(
    callback: str = Body(..., description="Callback URL"),
    query: Optional[str] = Body(None, description="Query string")
):
    """Create an event subscription hub to receive notifications"""
    try:
        result = await tmf637_client.create_hub(callback, query=query)
        return result
    except Exception as e:
        logger.error(f"Failed to create hub: {e}")
        raise

@app.delete("/api/hub/{hub_id}", tags=["hub"], operation_id="tmf637_delete_hub")
async def api_delete_hub(
    hub_id: str = Path(..., description="Hub ID")
):
    """Delete an event subscription hub"""
    try:
        result = await tmf637_client.delete_hub(hub_id)
        return result
    except Exception as e:
        logger.error(f"Failed to delete hub: {e}")
        raise

@app.get("/api/health", tags=["system"], operation_id="tmf637_health_check")
async def api_health_check():
    """Check the health status of the TMF637 API server"""
    try:
        result = await tmf637_client.health_check()
        return result
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise

# Add a standard health check endpoint
@app.get("/health")
async def health_check():
    """Health check for the MCP HTTP server"""
    try:
        # Check if we can reach the TMF637 API
        tmf637_health = await tmf637_client.health_check()
        return {
            "status": "healthy",
            "service": "TMF637 MCP HTTP Server",
            "tmf637_api": tmf637_health
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "service": "TMF637 MCP HTTP Server",
            "error": str(e)
        }

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "TMF637 Product Inventory API MCP Server",
        "version": "1.0.0",
        "description": "MCP server for TMF637 Product Inventory API",
        "endpoints": {
            "mcp": "/mcp",
            "api": "/api",
            "health": "/health",
            "docs": "/docs"
        }
    }

# Create FastApiMCP instance
mcp = FastApiMCP(
    app,
    name="TMF637 Product Inventory API MCP Server",
    description="MCP server for TMF637 Product Inventory API"
)

# Mount the MCP server
mcp.mount(mount_path="/mcp")

if __name__ == "__main__":
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8638"))
    
    print(f"Starting TMF637 Product Inventory API MCP Server...")
    print(f"Server: http://{host}:{port}")
    print(f"TMF637 API: {tmf637_client.base_url}")
    print(f"Documentation: http://{host}:{port}/docs")
    print(f"MCP Endpoint: http://{host}:{port}/mcp")
    print(f"API Endpoints: http://{host}:{port}/api")
    
    uvicorn.run(app, host=host, port=port)