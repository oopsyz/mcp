
#!/usr/bin/env python3
"""
The TMF629 MCP server.
"""
import os
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx
from fastapi import FastAPI, Query, Body, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mcp import FastApiMCP
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tmf-mcp-server")

class TMFClient:
    """Client for interacting with TMF APIs"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to TMF API"""
        url = urljoin(self.base_url + '/', endpoint.lstrip('/'))
        
        try:
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            
            if response.status_code == 204:
                return {"status": "success", "message": "Operation completed successfully"}
            
            return response.json()
        except Exception as e:
            logger.error(f"API request failed: {e}")
            raise
    
    async def list_customer(self, fields: Optional[str] = None, offset: Optional[int] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        """List or find Customer objects"""
        params = {}
        if fields:
            params['fields'] = fields
        if offset:
            params['offset'] = offset
        if limit:
            params['limit'] = limit
        
        return await self._make_request("get", "/customer", params=params)

    async def create_customer(self, customer: Dict[str, Any], fields: Optional[str] = None) -> Dict[str, Any]:
        """Creates a Customer"""
        params = {}
        if fields:
            params['fields'] = fields
        
        return await self._make_request("post", "/customer", json=customer, params=params)

    async def retrieve_customer(self, id: str, fields: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves a Customer by ID"""
        params = {}
        if fields:
            params['fields'] = fields
        
        return await self._make_request("get", f"/customer/{id}", params=params)

    async def patch_customer(self, id: str, customer: Dict[str, Any], fields: Optional[str] = None) -> Dict[str, Any]:
        """Updates partially a Customer"""
        params = {}
        if fields:
            params['fields'] = fields
        
        return await self._make_request("patch", f"/customer/{id}", json=customer, params=params)

    async def delete_customer(self, id: str) -> Dict[str, Any]:
        """Deletes a Customer"""
        return await self._make_request("delete", f"/customer/{id}")

# Initialize FastAPI app
app = FastAPI(
    title="TMF629 MCP Server",
    description="MCP server for TMF629 Customer Management API",
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

# Initialize TMF client
tmf_client = TMFClient(os.getenv("TMF_API_URL", "http://localhost:8080"))

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    await tmf_client.close()

@app.get("/customer", tags=["customer"], operation_id="tmf629_list_customer")
async def list_customer(
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to return"),
    offset: Optional[int] = Query(None, description="Requested index for start of resources"),
    limit: Optional[int] = Query(None, description="Requested number of resources")
):
    """List or find Customer objects"""
    return await tmf_client.list_customer(fields, offset, limit)

@app.post("/customer", tags=["customer"], operation_id="tmf629_create_customer")
async def create_customer(
    customer: Dict[str, Any] = Body(..., description="The Customer to be created"),
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to return")
):
    """Creates a Customer"""
    return await tmf_client.create_customer(customer, fields)

@app.get("/customer/{id}", tags=["customer"], operation_id="tmf629_retrieve_customer")
async def retrieve_customer(
    id: str = Path(..., description="Identifier of the Customer"),
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to return")
):
    """Retrieves a Customer by ID"""
    return await tmf_client.retrieve_customer(id, fields)

@app.patch("/customer/{id}", tags=["customer"], operation_id="tmf629_patch_customer")
async def patch_customer(
    id: str = Path(..., description="Identifier of the Customer"),
    customer: Dict[str, Any] = Body(..., description="The Customer to be updated"),
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to return")
):
    """Updates partially a Customer"""
    return await tmf_client.patch_customer(id, customer, fields)

@app.delete("/customer/{id}", tags=["customer"], operation_id="tmf629_delete_customer")
async def delete_customer(
    id: str = Path(..., description="Identifier of the Customer")
):
    """Deletes a Customer"""
    return await tmf_client.delete_customer(id)

# Add health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "TMF629 MCP Server"}

# Create FastApiMCP instance
mcp = FastApiMCP(
    app,
    name="TMF629 MCP Server",
    description="MCP server for TMF629 Customer Management API"
)

# Mount the MCP server
mcp.mount(mount_path="/mcp")

if __name__ == "__main__":
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8001"))
    
    print(f"Starting TMF629 MCP Server...")
    print(f"Server: http://{host}:{port}")
    print(f"TMF API: {tmf_client.base_url}")
    print(f"Documentation: http://{host}:{port}/docs")
    print(f"MCP Endpoint: http://{host}:{port}/mcp")
    
    uvicorn.run(app, host=host, port=port)
