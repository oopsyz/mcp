# Configuration for the MCP server connecting to a remote TMF620 API

# Remote TMF620 server URL (without trailing slash)
TMF620_API_URL = "http://localhost:8000"  # Updated to point to our local mock server

# Authentication settings
# Uncomment and fill in as needed for your remote server
AUTH_CONFIG = {
    # "api_key": "your_api_key_here",
    # "username": "your_username",
    # "password": "your_password",
    # "oauth_token": "your_oauth_token",
}

# API endpoints (relative to base URL)
ENDPOINTS = {
    "catalog_list": "/tmf-api/productCatalogManagement/v4/catalog",
    "catalog_detail": "/tmf-api/productCatalogManagement/v4/catalog/{id}",
    "product_offering_list": "/tmf-api/productCatalogManagement/v4/productOffering",
    "product_offering_detail": "/tmf-api/productCatalogManagement/v4/productOffering/{id}",
    "product_specification_list": "/tmf-api/productCatalogManagement/v4/productSpecification",
    "product_specification_detail": "/tmf-api/productCatalogManagement/v4/productSpecification/{id}",
    "product_offering_create": "/tmf-api/productCatalogManagement/v4/productOffering",
    "schema": "/tmf-api/productCatalogManagement/v4/schema"
}

# MCP server settings
MCP_SERVER_HOST = "localhost"
MCP_SERVER_PORT = 7001
MCP_SERVER_NAME = "TMF620 Product Catalog API"
MCP_SERVER_VERSION = "1.0.0"
MCP_SERVER_INSTRUCTIONS = """
This MCP server allows AI agents to interact with a remote TMF620 Product Catalog Management API.
You can use it to list, retrieve, and create catalogs, product offerings, and product specifications.
""" 