#!/usr/bin/env python3
"""
TMF760 Product Configuration API MCP HTTP Server (Ultra Simplified)
Uses FastApiMCP for automatic endpoint exposure
"""

import os
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx
from fastapi import FastAPI, Depends, Query, Body, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mcp import FastApiMCP
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tmf760-mcp-http-server")

class TMF760Client:
    """Client for interacting with TMF760 Product Configuration API"""
    
    def __init__(self, base_url: str = "http://localhost:8760"):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to TMF760 API"""
        url = urljoin(self.base_url + '/', endpoint.lstrip('/'))
        
        try:
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            
            if response.status_code == 204:
                return {"status": "success", "message": "Operation completed successfully"}
            
            return response.json()
        except httpx.HTTPStatusError as e:
            error_detail = f"HTTP {e.response.status_code}"
            try:
                error_body = e.response.json()
                error_detail = error_body.get("detail", error_detail)
            except:
                pass
            raise Exception(f"API request failed: {error_detail}")
        except Exception as e:
            raise Exception(f"Request failed: {str(e)}")
    
    # CheckProductConfiguration methods
    async def list_check_configurations(self, fields: Optional[str] = None, 
                                      offset: Optional[int] = None, 
                                      limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List CheckProductConfiguration objects"""
        params = {}
        if fields:
            params["fields"] = fields
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        
        return await self._make_request("GET", "/checkProductConfiguration", params=params)
    
    async def create_check_configuration(self, configuration: Dict[str, Any]) -> Dict[str, Any]:
        """Create a CheckProductConfiguration"""
        return await self._make_request("POST", "/checkProductConfiguration", json=configuration)
    
    async def get_check_configuration(self, config_id: str, fields: Optional[str] = None) -> Dict[str, Any]:
        """Get CheckProductConfiguration by ID"""
        params = {}
        if fields:
            params["fields"] = fields
        
        return await self._make_request("GET", f"/checkProductConfiguration/{config_id}", params=params)
    
    # QueryProductConfiguration methods
    async def list_query_configurations(self, fields: Optional[str] = None, 
                                       offset: Optional[int] = None, 
                                       limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List QueryProductConfiguration objects"""
        params = {}
        if fields:
            params["fields"] = fields
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        
        return await self._make_request("GET", "/queryProductConfiguration", params=params)
    
    async def create_query_configuration(self, configuration: Dict[str, Any]) -> Dict[str, Any]:
        """Create a QueryProductConfiguration"""
        return await self._make_request("POST", "/queryProductConfiguration", json=configuration)
    
    async def get_query_configuration(self, config_id: str, fields: Optional[str] = None) -> Dict[str, Any]:
        """Get QueryProductConfiguration by ID"""
        params = {}
        if fields:
            params["fields"] = fields
        
        return await self._make_request("GET", f"/queryProductConfiguration/{config_id}", params=params)
    
    # Hub management methods
    async def create_hub(self, callback: str, query: Optional[str] = None) -> Dict[str, Any]:
        """Create event subscription hub"""
        hub_data = {"callback": callback}
        if query:
            hub_data["query"] = query
        
        return await self._make_request("POST", "/hub", json=hub_data)
    
    async def delete_hub(self, hub_id: str) -> Dict[str, Any]:
        """Delete event subscription hub"""
        return await self._make_request("DELETE", f"/hub/{hub_id}")
    
    # Health check
    async def health_check(self) -> Dict[str, Any]:
        """Check API health status"""
        return await self._make_request("GET", "/health")

# Initialize FastAPI app
app = FastAPI(
    title="TMF760 MCP HTTP Server",
    description="HTTP interface for TMF760 Product Configuration API MCP tools",
    version="1.0.0"
)

# Add CORS middleware for remote access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize TMF760 client
tmf760_client = TMF760Client()

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    await tmf760_client.close()

# Define FastAPI endpoints that will be exposed as MCP tools

@app.get("/api/health", tags=["system"], operation_id="tmf760_health_check")
async def api_health_check():
    """Check the health status of the TMF760 API server"""
    try:
        result = await tmf760_client.health_check()
        return result
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise

@app.get("/api/check-configurations", tags=["check"], operation_id="tmf760_list_check_configurations")
async def api_list_check_configurations(
    fields: Optional[str] = Query(None, description="Fields to include in the response"),
    offset: Optional[int] = Query(None, description="Pagination offset"),
    limit: Optional[int] = Query(None, description="Pagination limit")
):
    """List CheckProductConfiguration objects with optional filtering and pagination"""
    try:
        result = await tmf760_client.list_check_configurations(
            fields=fields,
            offset=offset,
            limit=limit
        )
        return result
    except Exception as e:
        logger.error(f"Failed to list check configurations: {e}")
        raise

@app.post("/api/check-configurations", tags=["check"], operation_id="tmf760_create_check_configuration")
async def api_create_check_configuration(
    configuration: Dict[str, Any] = Body(..., description="Configuration data")
):
    """Create a new CheckProductConfiguration to validate product configuration"""
    try:
        result = await tmf760_client.create_check_configuration(configuration)
        return result
    except Exception as e:
        logger.error(f"Failed to create check configuration: {e}")
        raise

@app.get("/api/check-configurations/{config_id}", tags=["check"], operation_id="tmf760_get_check_configuration")
async def api_get_check_configuration(
    config_id: str = Path(..., description="Configuration ID"),
    fields: Optional[str] = Query(None, description="Fields to include in the response")
):
    """Retrieve a CheckProductConfiguration by ID"""
    try:
        result = await tmf760_client.get_check_configuration(config_id, fields=fields)
        return result
    except Exception as e:
        logger.error(f"Failed to get check configuration: {e}")
        raise

@app.get("/api/query-configurations", tags=["query"], operation_id="tmf760_list_query_configurations")
async def api_list_query_configurations(
    fields: Optional[str] = Query(None, description="Fields to include in the response"),
    offset: Optional[int] = Query(None, description="Pagination offset"),
    limit: Optional[int] = Query(None, description="Pagination limit")
):
    """List QueryProductConfiguration objects with optional filtering and pagination"""
    try:
        result = await tmf760_client.list_query_configurations(
            fields=fields,
            offset=offset,
            limit=limit
        )
        return result
    except Exception as e:
        logger.error(f"Failed to list query configurations: {e}")
        raise

@app.post("/api/query-configurations", tags=["query"], operation_id="tmf760_create_query_configuration")
async def api_create_query_configuration(
    configuration: Dict[str, Any] = Body(..., description="Configuration data")
):
    """Create a new QueryProductConfiguration to query product configurations"""
    try:
        result = await tmf760_client.create_query_configuration(configuration)
        return result
    except Exception as e:
        logger.error(f"Failed to create query configuration: {e}")
        raise

@app.get("/api/query-configurations/{config_id}", tags=["query"], operation_id="tmf760_get_query_configuration")
async def api_get_query_configuration(
    config_id: str = Path(..., description="Configuration ID"),
    fields: Optional[str] = Query(None, description="Fields to include in the response")
):
    """Retrieve a QueryProductConfiguration by ID"""
    try:
        result = await tmf760_client.get_query_configuration(config_id, fields=fields)
        return result
    except Exception as e:
        logger.error(f"Failed to get query configuration: {e}")
        raise

@app.post("/api/hub", tags=["hub"], operation_id="tmf760_create_hub")
async def api_create_hub(
    callback: str = Body(..., description="Callback URL"),
    query: Optional[str] = Body(None, description="Query string")
):
    """Create an event subscription hub to receive notifications"""
    try:
        result = await tmf760_client.create_hub(callback, query=query)
        return result
    except Exception as e:
        logger.error(f"Failed to create hub: {e}")
        raise

@app.delete("/api/hub/{hub_id}", tags=["hub"], operation_id="tmf760_delete_hub")
async def api_delete_hub(
    hub_id: str = Path(..., description="Hub ID")
):
    """Delete an event subscription hub"""
    try:
        result = await tmf760_client.delete_hub(hub_id)
        return result
    except Exception as e:
        logger.error(f"Failed to delete hub: {e}")
        raise

# Add a standard health check endpoint
@app.get("/health")
async def health_check():
    """Health check for the MCP HTTP server"""
    try:
        # Check if we can reach the TMF760 API
        tmf760_health = await tmf760_client.health_check()
        return {
            "status": "healthy",
            "service": "TMF760 MCP HTTP Server",
            "tmf760_api": tmf760_health
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "service": "TMF760 MCP HTTP Server",
            "error": str(e)
        }

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "TMF760 MCP HTTP Server",
        "version": "1.0.0",
        "description": "HTTP interface for TMF760 Product Configuration API MCP tools",
        "endpoints": {
            "mcp": "/mcp",
            "api": "/api",
            "health": "/health",
            "docs": "/docs"
        }
    }

# Create FastApiMCP instance to expose FastAPI endpoints as MCP tools
mcp = FastApiMCP(
    app,
    name="TMF760 MCP Server",
    description="MCP server for TMF760 Product Configuration API"
)

# Mount the MCP server
mcp.mount(mount_path="/mcp")

if __name__ == "__main__":
    # Get configuration from environment
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8761"))
    tmf760_url = os.getenv("TMF760_BASE_URL", "http://localhost:8760")
    
    # Update TMF760 client base URL
    tmf760_client.base_url = tmf760_url.rstrip('/')
    
    print(f"Starting TMF760 MCP HTTP Server...")
    print(f"Server: http://{host}:{port}")
    print(f"TMF760 API: {tmf760_url}")
    print(f"Documentation: http://{host}:{port}/docs")
    print(f"MCP Endpoint: http://{host}:{port}/mcp")
    print(f"API Endpoints: http://{host}:{port}/api")
    
    uvicorn.run(app, host=host, port=port)