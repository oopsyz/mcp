
#!/usr/bin/env python3
"""
Client for TMF629 API.
"""
import httpx
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tmf-client")

class TMF629Client:
    """Client for interacting with TMF629 Customer Management API"""
    
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
