from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mcp import FastApiMCP
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from contextlib import asynccontextmanager
import requests
import json
import os
import logging
import asyncio
import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("tmf620_mcp_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("tmf620-mcp")

# Global variables
config = None

def load_config() -> Dict[str, Any]:
    """Load configuration from config file or environment variables."""
    config = {}
    
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Default config path is config.json in the same directory as the script
    default_config_path = os.path.join(script_dir, 'config.json')
    
    # Allow overriding with environment variable
    config_path = os.environ.get('TMF620_CONFIG_PATH', default_config_path)
    
    try:
        logger.info(f"Attempting to load config from {config_path}")
        with open(config_path) as config_file:
            config = json.load(config_file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Could not load config from {config_path}: {e}")
        logger.info("Falling back to environment variables")
    
    # Fallback to environment variables if config values are missing
    if 'tmf620_api' not in config:
        config['tmf620_api'] = {}
    
    config['tmf620_api']['url'] = (
        config.get('tmf620_api', {}).get('url') or 
        os.environ.get('TMF620_API_URL', 'http://localhost:8801/tmf-api/productCatalogManagement/v4')
    )
    
    if 'mcp_server' not in config:
        config['mcp_server'] = {}
    
    config['mcp_server']['host'] = (
        config.get('mcp_server', {}).get('host') or 
        os.environ.get('MCP_HOST', 'localhost')
    )
    config['mcp_server']['port'] = (
        config.get('mcp_server', {}).get('port') or 
        int(os.environ.get('MCP_PORT', '7701'))
    )
    config['mcp_server']['name'] = (
        config.get('mcp_server', {}).get('name') or 
        os.environ.get('MCP_NAME', 'TMF620 Product Catalog API')
    )
    
    # Set default endpoints if not provided
    if 'endpoints' not in config:
        config['endpoints'] = {
            "catalog_list": "/catalog",
            "catalog_detail": "/catalog/{id}",
            "product_offering_list": "/productOffering",
            "product_offering_detail": "/productOffering/{id}",
            "product_specification_list": "/productSpecification",
            "product_specification_detail": "/productSpecification/{id}",
            "product_offering_create": "/productOffering",
            "schema": "/schema"
        }
    
    logger.info(f"TMF620 API URL: {config['tmf620_api']['url']}")
    logger.info(f"MCP Server: {config['mcp_server']['host']}:{config['mcp_server']['port']}")
        
    return config

# Get the TMF620 API base URL from config
def get_api_base_url():
    return config['tmf620_api']['url']

# Pydantic models
class CatalogRequest(BaseModel):
    catalog_id: str

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

@asynccontextmanager
async def lifespan(app: FastAPI):
    global config
    try:
        # Load configuration
        config = load_config()
        
        # Test API connection
        test_connection()
        logger.info("Successfully connected to TMF620 API")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to initialize TMF620 MCP server: {e}")
        raise

def test_connection():
    """Test connection to TMF620 API"""
    try:
        url = f"{config['tmf620_api']['url']}/catalog"
        response = requests.get(url, timeout=10)
        if response.status_code == 404:
            # 404 is acceptable - means API is running but endpoint might not exist
            logger.info("TMF620 API is reachable (404 response is normal for empty catalog)")
        else:
            response.raise_for_status()
            logger.info("TMF620 API connection test successful")
    except requests.exceptions.ConnectionError:
        raise Exception(f"Could not connect to TMF620 API at {config['tmf620_api']['url']}. Is the mock server running?")
    except Exception as e:
        logger.warning(f"API connection test warning: {e}")

# Helper function to make API requests
def api_request(method: str, endpoint: str, params: Optional[Dict] = None, json_data: Optional[Dict] = None, timeout: int = 30) -> Dict[str, Any]:
    """Execute API request with comprehensive error handling"""
    if not endpoint.startswith("/"):
        raise ValueError("Endpoint must start with '/'")
    
    valid_methods = ["GET", "POST", "PUT", "DELETE"]
    if method.upper() not in valid_methods:
        raise ValueError(f"Invalid method {method}. Must be one of {valid_methods}")
    
    url = f"{config['tmf620_api']['url']}{endpoint}"
    
    # Set up headers
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "TMF620-MCP-Server/1.0"
    }
    
    logger.info(f"Making {method} request to {url}")
    try:
        response = requests.request(
            method, 
            url, 
            params=params, 
            json=json_data, 
            headers=headers,
            timeout=timeout
        )
        response.raise_for_status()
        
        # Handle empty responses
        if not response.content:
            return {}
            
        return response.json()
        
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error {e.response.status_code}: {e}")
        # Try to get error details from response
        error_detail = "Unknown error"
        try:
            if e.response.content:
                error_detail = e.response.json()
        except:
            error_detail = e.response.text if e.response.text else f"HTTP {e.response.status_code}"
        
        raise Exception(f"TMF620 API error: {e.response.status_code} - {error_detail}")
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error to {url}")
        raise Exception(f"Could not connect to TMF620 API at {config['tmf620_api']['url']}. Is the mock server running on the correct port?")
    except requests.exceptions.Timeout:
        logger.error(f"Request timeout to {url}")
        raise Exception(f"TMF620 API request timed out after {timeout} seconds")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")
        raise Exception(f"Error making request to TMF620 API: {str(e)}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        raise Exception("Invalid JSON response from TMF620 API")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise Exception(f"Unexpected error: {str(e)}")

# Create FastAPI app
app = FastAPI(
    title="TMF620 Product Catalog MCP Server",
    description="MCP server for TMF620 Product Catalog Management API queries and operations",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# FastAPI endpoints
@app.get("/health", operation_id="get_health_status")
async def health_check():
    """Health Check
    
    Check the health of the TMF620 MCP server and its connection to the TMF620 API.
    This endpoint verifies that the server is running and can communicate with the backend API.
    """
    try:
        # Test API connection
        api_request("GET", config["endpoints"]["catalog_list"])
        return {
            "status": "healthy", 
            "api_connection": "successful",
            "api_url": config['tmf620_api']['url'],
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "healthy", 
            "api_connection": "failed",
            "api_url": config['tmf620_api']['url'],
            "error": str(e),
            "timestamp": datetime.datetime.now().isoformat()
        }

@app.get("/catalogs", operation_id="list_catalogs")
async def list_catalogs_endpoint():
    """List Product Catalogs (LLM Tool Guidance)
    
    **When to use this tool:**
    - To discover what product catalogs exist in the TMF620 system
    - As a starting point before querying specific catalog details or product offerings
    - When you need an overview of all available catalogs
    
    **What this returns:**
    - Array of catalog objects with basic information (ID, name, description, lifecycle status)
    - Empty array if no catalogs exist
    
    **Next steps after using this tool:**
    - Use get_catalog() with a specific catalog_id for detailed information
    - Use list_product_offerings() to see products within a specific catalog
    - Use create_product_offering() to add products to a catalog
    
    **Example usage:**
    - "Show me all available product catalogs"
    - "What catalogs do we have in the system?"
    - "List all catalogs so I can choose one to work with"
    """
    try:
        result = await asyncio.to_thread(api_request, "GET", config["endpoints"]["catalog_list"])
        return ApiResponse(result=result, timestamp=datetime.datetime.now().isoformat())
    except Exception as e:
        logger.error(f"Error listing catalogs: {e}")
        return ApiResponse(error=str(e), timestamp=datetime.datetime.now().isoformat())

@app.get("/catalogs/{catalog_id}", operation_id="get_catalog")
async def get_catalog_endpoint(catalog_id: str):
    """Get Specific Catalog Details (LLM Tool Guidance)
    
    **When to use this tool:**
    - When you need complete details about a specific product catalog
    - To get catalog metadata including name, description, lifecycle status, and associated information
    - Before performing operations on a catalog (to verify it exists and get its properties)
    
    **What this returns:**
    - Complete catalog object with all properties and metadata
    - Error if catalog doesn't exist
    
    **Parameters:**
    - catalog_id: The unique identifier of the catalog to retrieve
    
    **Next steps after using this tool:**
    - Use list_product_offerings() to see products in this catalog
    - Use create_product_offering() to add products to this catalog
    
    **Example usage:**
    - "Get details for catalog cat-001"
    - "Show me information about the electronics catalog"
    - "What are the properties of catalog ID xyz-123?"
    """
    try:
        endpoint = config["endpoints"]["catalog_detail"].format(id=catalog_id)
        result = await asyncio.to_thread(api_request, "GET", endpoint)
        return ApiResponse(result=result, timestamp=datetime.datetime.now().isoformat())
    except Exception as e:
        logger.error(f"Error getting catalog {catalog_id}: {e}")
        return ApiResponse(error=str(e), timestamp=datetime.datetime.now().isoformat())

@app.get("/product-offerings", operation_id="list_product_offerings")
async def list_product_offerings_endpoint(catalog_id: Optional[str] = None):
    """List Product Offerings (LLM Tool Guidance)
    
    **When to use this tool:**
    - To browse available products and services in the TMF620 system
    - To see all product offerings across all catalogs or within a specific catalog
    - When you need to find existing products before creating new ones
    
    **What this returns:**
    - Array of product offering objects with basic information (ID, name, description, catalog association)
    - Can be filtered by catalog_id to show only products in a specific catalog
    - Empty array if no product offerings exist
    
    **Parameters:**
    - catalog_id (optional): Filter results to show only offerings in this specific catalog
    
    **Next steps after using this tool:**
    - Use get_product_offering() with a specific offering_id for detailed information
    - Use create_product_offering() to add new products
    
    **Example usage:**
    - "Show me all product offerings"
    - "List products in the electronics catalog"
    - "What offerings are available in catalog cat-001?"
    """
    try:
        params = {}
        if catalog_id and catalog_id.lower() not in ["null", ""]:
            params["catalog.id"] = catalog_id
        
        result = await asyncio.to_thread(api_request, "GET", config["endpoints"]["product_offering_list"], params=params)
        return ApiResponse(result=result, timestamp=datetime.datetime.now().isoformat())
    except Exception as e:
        logger.error(f"Error listing product offerings: {e}")
        return ApiResponse(error=str(e), timestamp=datetime.datetime.now().isoformat())

@app.get("/product-offerings/{offering_id}", operation_id="get_product_offering")
async def get_product_offering_endpoint(offering_id: str):
    """Get Specific Product Offering Details (LLM Tool Guidance)
    
    **When to use this tool:**
    - When you need complete details about a specific product offering
    - To get product information including pricing, specifications, lifecycle status, and catalog association
    - Before modifying or working with a specific product offering
    
    **What this returns:**
    - Complete product offering object with all properties, pricing information, and related specifications
    - Error if product offering doesn't exist
    
    **Parameters:**
    - offering_id: The unique identifier of the product offering to retrieve
    
    **Example usage:**
    - "Get details for product offering prod-001"
    - "Show me information about the premium service offering"
    - "What are the specifications for offering ID xyz-456?"
    """
    try:
        endpoint = config["endpoints"]["product_offering_detail"].format(id=offering_id)
        result = await asyncio.to_thread(api_request, "GET", endpoint)
        return ApiResponse(result=result, timestamp=datetime.datetime.now().isoformat())
    except Exception as e:
        logger.error(f"Error getting product offering {offering_id}: {e}")
        return ApiResponse(error=str(e), timestamp=datetime.datetime.now().isoformat())

@app.post("/product-offerings", operation_id="create_product_offering")
async def create_product_offering_endpoint(request: ProductOfferingRequest):
    """Create New Product Offering (LLM Tool Guidance)
    
    **When to use this tool:**
    - When users want to add new products or services to their catalog
    - To create product offerings that can be sold or provided to customers
    - When expanding the product portfolio in a specific catalog
    
    **What this does:**
    - Creates a new product offering with the specified name, description, and catalog association
    - Returns the created product offering object with generated ID and metadata
    
    **Required Parameters:**
    - name: The name of the new product offering
    - description: Detailed description of the product offering
    - catalog_id: The ID of the catalog where this offering should be created
    
    **Prerequisites:**
    - The specified catalog_id must exist (use list_catalogs() to verify)
    - The name should be unique within the catalog
    
    **Example usage:**
    - "Create a new premium service offering in catalog cat-001"
    - "Add a basic internet package to the telecom catalog"
    - "Create a new product called 'Enterprise Solution' with description 'Comprehensive business package'"
    """
    try:
        payload = {
            "name": request.name,
            "description": request.description,
            "catalogId": request.catalog_id,
            "lifecycleStatus": "Active",
            "version": "1.0"
        }
        
        result = await asyncio.to_thread(api_request, "POST", config["endpoints"]["product_offering_create"], json_data=payload)
        return ApiResponse(result=result, timestamp=datetime.datetime.now().isoformat())
    except Exception as e:
        logger.error(f"Error creating product offering: {e}")
        return ApiResponse(error=str(e), timestamp=datetime.datetime.now().isoformat())

@app.get("/product-specifications", operation_id="list_product_specifications")
async def list_product_specifications_endpoint():
    """List Product Specifications (LLM Tool Guidance)
    
    **When to use this tool:**
    - To discover available product templates and technical specifications in the TMF620 system
    - When you need to see what specification templates can be used to create product offerings
    - To browse existing technical specifications before creating new ones
    
    **What this returns:**
    - Array of product specification objects with basic information (ID, name, description, version, lifecycle status)
    - Empty array if no product specifications exist
    
    **Next steps after using this tool:**
    - Use get_product_specification() with a specific specification_id for detailed information
    - Use create_product_specification() to add new specification templates
    - Use these specifications when creating product offerings
    
    **Example usage:**
    - "Show me all product specifications"
    - "List available specification templates"
    - "What technical specifications do we have?"
    """
    try:
        result = await asyncio.to_thread(api_request, "GET", config["endpoints"]["product_specification_list"])
        return ApiResponse(result=result, timestamp=datetime.datetime.now().isoformat())
    except Exception as e:
        logger.error(f"Error listing product specifications: {e}")
        return ApiResponse(error=str(e), timestamp=datetime.datetime.now().isoformat())

@app.get("/product-specifications/{specification_id}", operation_id="get_product_specification")
async def get_product_specification_endpoint(specification_id: str):
    """Get Specific Product Specification Details (LLM Tool Guidance)
    
    **When to use this tool:**
    - When you need complete technical details about a specific product specification
    - To get specification information including version, lifecycle status, and specification attributes
    - Before using a specification template to create product offerings
    
    **What this returns:**
    - Complete product specification object with all technical details and attributes
    - Error if product specification doesn't exist
    
    **Parameters:**
    - specification_id: The unique identifier of the product specification to retrieve
    
    **Example usage:**
    - "Get details for product specification spec-001"
    - "Show me the technical details of the broadband specification"
    - "What are the attributes of specification ID tech-456?"
    """
    try:
        endpoint = config["endpoints"]["product_specification_detail"].format(id=specification_id)
        result = await asyncio.to_thread(api_request, "GET", endpoint)
        return ApiResponse(result=result, timestamp=datetime.datetime.now().isoformat())
    except Exception as e:
        logger.error(f"Error getting product specification {specification_id}: {e}")
        return ApiResponse(error=str(e), timestamp=datetime.datetime.now().isoformat())

@app.post("/product-specifications", operation_id="create_product_specification")
async def create_product_specification_endpoint(request: ProductSpecificationRequest):
    """Create New Product Specification (LLM Tool Guidance)
    
    **When to use this tool:**
    - When you need to define technical specifications that can later be used to create product offerings
    - To create reusable specification templates for similar products
    - When establishing technical standards for product categories
    
    **What this does:**
    - Creates a new product specification template with the specified name, description, and version
    - Returns the created specification object with generated ID and metadata
    
    **Required Parameters:**
    - name: The name of the new product specification
    - description: Detailed technical description of the specification
    - version: Version number (defaults to "1.0")
    
    **Next steps after using this tool:**
    - Use the created specification when creating product offerings
    - Reference this specification in product offering creation
    
    **Example usage:**
    - "Create a new broadband specification template"
    - "Add a mobile service specification with version 2.0"
    - "Create a technical spec for enterprise solutions"
    """
    try:
        payload = {
            "name": request.name,
            "description": request.description,
            "version": request.version,
            "lifecycleStatus": "Active"
        }
        
        result = await asyncio.to_thread(api_request, "POST", config["endpoints"]["product_specification_list"], json_data=payload)
        return ApiResponse(result=result, timestamp=datetime.datetime.now().isoformat())
    except Exception as e:
        logger.error(f"Error creating product specification: {e}")
        return ApiResponse(error=str(e), timestamp=datetime.datetime.now().isoformat())

@app.get("/server-config", operation_id="get_server_config")
async def server_config():
    """Get Server Configuration
    
    Returns the current TMF620 MCP server configuration including API connection details and operational status.
    Useful for understanding the current server setup and connection information.
    """
    return {
        "tmf620_api_url": config['tmf620_api']['url'],
        "mcp_server_host": config['mcp_server']['host'],
        "mcp_server_port": config['mcp_server']['port'],
        "server_name": config['mcp_server']['name'],
        "timestamp": datetime.datetime.now().isoformat()
    }

# Mount MCP server
mcp = FastApiMCP(app)
mcp.mount()

def main():
    """Main entry point for the TMF620 MCP server"""
    import uvicorn
    
    # Load config for main function
    global config
    if config is None:
        config = load_config()
    
    host = config['mcp_server']['host']
    port = config['mcp_server']['port']
    
    print(f"Starting TMF620 MCP server on http://{host}:{port}")
    print(f"TMF620 API URL: {config['tmf620_api']['url']}")
    print(f"Health check: http://{host}:{port}/health")
    print(f"API Documentation: http://{host}:{port}/docs")
    
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    main()