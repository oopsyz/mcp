#!/usr/bin/env python3
"""
TMF637 Product Inventory API Client
Client for interacting with TMF637 Product Inventory API
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tmf637-client")

class TMF637Client:
    """Client for interacting with TMF637 Product Inventory API"""
    
    def __init__(self, base_url: str = "http://localhost:8637"):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to TMF637 API"""
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
            logger.error(f"API request failed: {error_detail}")
            raise Exception(f"API request failed: {error_detail}")
        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            raise Exception(f"Request failed: {str(e)}")
    
    # Product methods
    async def list_products(self, fields: Optional[str] = None, 
                          offset: Optional[int] = None, 
                          limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List Product objects"""
        params = {}
        if fields:
            params["fields"] = fields
        if offset is not None:
            params["offset"] = offset
        if limit is not None:
            params["limit"] = limit
        
        return await self._make_request("GET", "/product", params=params)
    
    async def create_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Product"""
        return await self._make_request("POST", "/product", json=product)
    
    async def get_product(self, product_id: str, fields: Optional[str] = None) -> Dict[str, Any]:
        """Get Product by ID"""
        params = {}
        if fields:
            params["fields"] = fields
        
        return await self._make_request("GET", f"/product/{product_id}", params=params)
    
    async def update_product(self, product_id: str, product: Dict[str, Any]) -> Dict[str, Any]:
        """Update a Product"""
        return await self._make_request("PUT", f"/product/{product_id}", json=product)
    
    async def patch_product(self, product_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        """Patch a Product"""
        return await self._make_request("PATCH", f"/product/{product_id}", json=patch)
    
    async def delete_product(self, product_id: str) -> Dict[str, Any]:
        """Delete a Product"""
        return await self._make_request("DELETE", f"/product/{product_id}")
    
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