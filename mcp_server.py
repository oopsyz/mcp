import requests
import logging
from mcp.server.fastmcp import FastMCP
import config
import asyncio
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("tmf620-mcp")

# Helper function to make API requests
def api_request(method, endpoint, params=None, json=None):
    if not endpoint.startswith("/"):
        raise ValueError("Endpoint must start with '/'")
    
    valid_methods = ["GET", "POST", "PUT", "DELETE"]
    if method.upper() not in valid_methods:
        raise ValueError(f"Invalid method {method}. Must be one of {valid_methods}")
    
    url = f"{config.TMF620_API_URL}{endpoint}"
    
    # Set up headers with authentication if provided
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Add authentication headers if configured
    if hasattr(config, 'AUTH_CONFIG'):
        if 'api_key' in config.AUTH_CONFIG:
            headers["Authorization"] = f"Bearer {config.AUTH_CONFIG['api_key']}"
        elif 'oauth_token' in config.AUTH_CONFIG:
            headers["Authorization"] = f"Bearer {config.AUTH_CONFIG['oauth_token']}"
        elif 'username' in config.AUTH_CONFIG and 'password' in config.AUTH_CONFIG:
            import base64
            auth_str = f"{config.AUTH_CONFIG['username']}:{config.AUTH_CONFIG['password']}"
            encoded = base64.b64encode(auth_str.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
    
    logger.info(f"Making {method} request to {url}")
    try:
        response = requests.request(method, url, params=params, json=json, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error: {e}")
        # Try to get error details from response
        error_detail = "Unknown error"
        try:
            error_detail = response.json()
        except:
            error_detail = response.text
        
        raise Exception(f"TMF620 API error: {e.response.status_code} - {error_detail}")
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error to {url}")
        raise Exception(f"Could not connect to TMF620 API at {config.TMF620_API_URL}")
    except requests.exceptions.Timeout:
        logger.error(f"Request timeout to {url}")
        raise Exception("TMF620 API request timed out")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")
        raise Exception(f"Error making request to TMF620 API: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

# Replace existing Server initialization with:
mcp = FastMCP(
    name=config.MCP_SERVER_NAME,
    version=config.MCP_SERVER_VERSION,
    description="TMF620 Catalog Interface",
    instructions=config.MCP_SERVER_INSTRUCTIONS,  # Pass instructions during initialization
    host=config.MCP_SERVER_HOST,
    port=config.MCP_SERVER_PORT
)

# Update tool registration using SDK's preferred pattern
@mcp.tool(
    name="get_catalog",
    description="Get specific catalog by ID"
)
async def get_catalog(catalog_id: str) -> dict:
    """Catalog detail handler"""
    try:
        endpoint = config.ENDPOINTS["catalog_detail"].format(id=catalog_id)
        return await asyncio.to_thread(api_request, "GET", endpoint)
    except Exception as e:
        logger.error(f"Error getting catalog: {e}")
        return {"error": str(e)}

# Define tools using the @mcp.tool decorator
@mcp.tool(
    name="health",
    description="Check server and API connection health"
)
async def health_check() -> dict:
    """Health check endpoint handler"""
    try:
        api_request("GET", config.ENDPOINTS["catalog_list"])
        return {"status": "healthy", "connection": "successful"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@mcp.tool(
    name="list_catalogs",
    description="List all product catalogs"
)
async def list_catalogs() -> list:
    """Catalog listing handler"""
    return await asyncio.to_thread(api_request, "GET", config.ENDPOINTS["catalog_list"])

@mcp.resource("tmf620://catalogs")
async def catalog_schema() -> str:
    """Expose TMF620 API schema as a resource"""
    return json.dumps(api_request("GET", config.ENDPOINTS["schema"]))

@mcp.tool(
    name="create_product_offering",
    description="Create a new product offering"
)
async def create_product_offering(name: str, description: str, catalog_id: str) -> dict:
    """Create a new product offering in the specified catalog"""
    # Prepare the request payload
    payload = {
        "name": name,
        "description": description,
        "catalogId": catalog_id,
        # Other required fields...
    }
    
    # Make the API call
    endpoint = config.ENDPOINTS["product_offering_create"]
    return await asyncio.to_thread(api_request, "POST", endpoint, json=payload)

@mcp.tool(
    name="list_product_offerings",
    description="List all product offerings in a catalog"
)
async def list_product_offerings(catalog_id: str = None) -> dict:
    """List product offerings, optionally filtered by catalog ID"""
    try:
        # Prepare query parameters if catalog_id is provided
        params = {}
        if catalog_id and catalog_id.lower() != "null" and catalog_id != "":
            params["catalog.id"] = catalog_id
        
        # Make the API call
        endpoint = config.ENDPOINTS["product_offering_list"]
        return await asyncio.to_thread(api_request, "GET", endpoint, params=params)
    except Exception as e:
        logger.error(f"Error listing product offerings: {e}")
        return {"error": str(e)}

@mcp.tool(
    name="get_product_offering",
    description="Get a specific product offering by ID"
)
async def get_product_offering(offering_id: str) -> dict:
    """Get detailed information about a specific product offering"""
    try:
        endpoint = config.ENDPOINTS["product_offering_detail"].format(id=offering_id)
        return await asyncio.to_thread(api_request, "GET", endpoint)
    except Exception as e:
        logger.error(f"Error getting product offering: {e}")
        return {"error": str(e)}

@mcp.tool(
    name="list_product_specifications",
    description="List all product specifications"
)
async def list_product_specifications() -> dict:
    """List all product specifications in the system"""
    try:
        endpoint = config.ENDPOINTS["product_specification_list"]
        return await asyncio.to_thread(api_request, "GET", endpoint)
    except Exception as e:
        logger.error(f"Error listing product specifications: {e}")
        return {"error": str(e)}

@mcp.tool(
    name="get_product_specification",
    description="Get a specific product specification by ID"
)
async def get_product_specification(specification_id: str) -> dict:
    """Get detailed information about a specific product specification"""
    try:
        endpoint = config.ENDPOINTS["product_specification_detail"].format(id=specification_id)
        return await asyncio.to_thread(api_request, "GET", endpoint)
    except Exception as e:
        logger.error(f"Error getting product specification: {e}")
        return {"error": str(e)}

@mcp.tool(
    name="create_product_specification",
    description="Create a new product specification"
)
async def create_product_specification(name: str, description: str, version: str = "1.0") -> dict:
    """Create a new product specification with the given details"""
    try:
        # Prepare the request payload
        payload = {
            "name": name,
            "description": description,
            "version": version,
            "lifecycleStatus": "Active",
            # Add any other required fields based on TMF620 API requirements
        }
        
        # Make the API call
        endpoint = config.ENDPOINTS["product_specification_list"]  # POST to the list endpoint to create
        return await asyncio.to_thread(api_request, "POST", endpoint, json=payload)
    except Exception as e:
        logger.error(f"Error creating product specification: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    logger.info(f"Starting MCP server for remote TMF620 API at {config.TMF620_API_URL}")
    logger.info(f"MCP server will be available at http://{config.MCP_SERVER_HOST}:{config.MCP_SERVER_PORT}")
    
    # Run with SSE transport
    mcp.run(transport='sse')