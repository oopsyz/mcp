#!/usr/bin/env python3
"""
TMF637 Product Inventory API Mock Server
Implements a mock TMF637 API based on the OpenAPI specification
"""

import os
import json
import logging
import yaml
import time
import asyncio
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Body, Path, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tmf637-mock-server")

def load_openapi_spec(yaml_path: str) -> Dict[str, Any]:
    """Load and parse the OpenAPI specification from a YAML file"""
    try:
        # Try different encodings to handle potential encoding issues
        encodings = ['utf-8', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(yaml_path, 'r', encoding=encoding) as file:
                    return yaml.safe_load(file)
            except UnicodeDecodeError:
                # Try the next encoding
                continue
        
        # If all encodings fail, try with errors='replace'
        with open(yaml_path, 'r', encoding='utf-8', errors='replace') as file:
            return yaml.safe_load(file)
    except Exception as e:
        logger.error(f"Failed to load OpenAPI spec: {e}")
        raise

def generate_sample_data(schema: Dict[str, Any], path: str = "", property_name: str = "") -> Any:
    """Generate sample data based on an OpenAPI schema with more realistic values"""
    import random
    import uuid
    from datetime import datetime, timedelta
    
    # Handle allOf schema composition
    if 'allOf' in schema:
        result = {}
        for sub_schema in schema['allOf']:
            sub_data = generate_sample_data(sub_schema, path, property_name)
            if isinstance(sub_data, dict):
                result.update(sub_data)
        return result
    
    if 'type' not in schema:
        # Handle $ref references or empty schemas
        if '$ref' in schema:
            # For simplicity, return an empty object for references
            return {}
        # If no type is specified, assume it's an object and try to generate basic product data
        if not schema or schema == {}:
            return {
                "name": f"Sample Product {random.randint(1, 100)}",
                "description": "Sample product description",
                "status": random.choice(["active", "suspended", "terminated"]),
                "productType": "service"
            }
        return {}
    
    schema_type = schema['type']
    
    if schema_type == 'object':
        result = {}
        for prop_name, prop_schema in schema.get('properties', {}).items():
            # Pass the property path for context-aware generation
            prop_path = f"{path}.{prop_name}" if path else prop_name
            result[prop_name] = generate_sample_data(prop_schema, prop_path, prop_name)
        return result
    
    elif schema_type == 'array':
        items_schema = schema.get('items', {})
        # Generate 1-3 items for arrays
        count = random.randint(1, 3)
        return [generate_sample_data(items_schema, f"{path}[{i}]", property_name) for i in range(count)]
    
    elif schema_type == 'string':
        # Generate more realistic string values based on property name or format
        if schema.get('format') == 'date-time':
            # Generate a random date within the last year
            days_ago = random.randint(0, 365)
            dt = datetime.now() - timedelta(days=days_ago)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        elif schema.get('format') == 'date':
            days_ago = random.randint(0, 365)
            dt = datetime.now() - timedelta(days=days_ago)
            return dt.strftime("%Y-%m-%d")
        
        elif schema.get('format') == 'uri':
            domains = ["api.example.com", "inventory.telco.com", "tmf.org"]
            paths = ["products", "services", "inventory", "catalog"]
            return f"https://{random.choice(domains)}/{random.choice(paths)}/{uuid.uuid4()}"
        
        elif schema.get('format') == 'email':
            domains = ["example.com", "telco.org", "provider.net"]
            names = ["user", "customer", "admin", "support"]
            return f"{random.choice(names)}{random.randint(1, 999)}@{random.choice(domains)}"
        
        elif 'enum' in schema:
            # Randomly select from enum values
            return random.choice(schema['enum'])
        
        else:
            # Generate contextual string based on property name
            prop_lower = property_name.lower()
            
            if 'id' in prop_lower:
                return str(uuid.uuid4())
            elif 'name' in prop_lower:
                if 'product' in prop_lower or 'product' in path.lower():
                    products = ["Fiber Broadband", "5G Mobile", "Cloud Storage", "IoT Platform", "TV Streaming"]
                    return f"{random.choice(products)} {random.choice(['Basic', 'Pro', 'Enterprise', 'Premium'])}"
                else:
                    return f"Sample {property_name.title()} {random.randint(1, 100)}"
            elif 'description' in prop_lower:
                return f"This is a sample description for {path} with randomly generated content."
            elif 'status' in prop_lower:
                statuses = ["active", "suspended", "terminated", "pending", "reserved"]
                return random.choice(statuses)
            elif 'type' in prop_lower:
                types = ["physical", "virtual", "service", "bundle", "resource"]
                return random.choice(types)
            elif 'version' in prop_lower:
                return f"{random.randint(1, 5)}.{random.randint(0, 9)}.{random.randint(0, 9)}"
            elif 'href' in prop_lower:
                return f"/tmf-api/productInventory/v5/product/{uuid.uuid4()}"
            else:
                return f"sample-{property_name}-{random.randint(1000, 9999)}"
    
    elif schema_type == 'number':
        # Generate more realistic numbers
        if 'price' in property_name.lower() or 'cost' in property_name.lower():
            # Generate price with 2 decimal places
            return round(random.uniform(9.99, 299.99), 2)
        elif 'percentage' in property_name.lower() or 'rate' in property_name.lower():
            # Generate percentage
            return round(random.uniform(0, 100), 2)
        else:
            # Generate random float
            return round(random.uniform(1, 1000), 2)
    
    elif schema_type == 'integer':
        # Generate contextual integers
        if 'count' in property_name.lower() or 'quantity' in property_name.lower():
            return random.randint(1, 10)
        elif 'year' in property_name.lower():
            return random.randint(2020, 2025)
        elif 'age' in property_name.lower():
            return random.randint(18, 80)
        else:
            return random.randint(1, 100)
    
    elif schema_type == 'boolean':
        return random.choice([True, False])
    
    else:
        return None

def create_mock_api(openapi_spec: Dict[str, Any], delay: float = 0) -> FastAPI:
    """Create a FastAPI application based on the OpenAPI specification"""
    info = openapi_spec.get('info', {})
    app = FastAPI(
        title=info.get('title', 'TMF637 Product Inventory API Mock Server'),
        description=info.get('description', 'Mock implementation of TMF637 Product Inventory API'),
        version=info.get('version', '1.0.0')
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # In-memory storage for mock data
    storage = {}
    
    # Pre-populate with some realistic product inventory data
    def initialize_product_inventory():
        """Pre-populate the product inventory with realistic sample data"""
        # Find the product schema from components
        components = openapi_spec.get('components', {})
        schemas = components.get('schemas', {})
        product_schema = schemas.get('Product', {})
        
        if not product_schema:
            logger.warning("Could not find Product schema in OpenAPI spec for pre-population")
            logger.info(f"Available schemas: {list(schemas.keys())}")
            # Create a fallback schema for basic product structure
            product_schema = {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "status": {"type": "string", "enum": ["active", "suspended", "terminated"]},
                    "productType": {"type": "string"},
                    "creationDate": {"type": "string", "format": "date-time"},
                    "lastUpdate": {"type": "string", "format": "date-time"}
                }
            }
            logger.info("Using fallback Product schema")
            
        # Generate some initial products
        products = []
        logger.info(f"Product schema found: {bool(product_schema)}")
        logger.info(f"Product schema keys: {list(product_schema.keys()) if product_schema else 'None'}")
        
        for i in range(5):  # Create 5 initial products
            product = generate_sample_data(product_schema, "Product", "Product")
            # Ensure ID is set
            if isinstance(product, dict) and 'id' not in product:
                product['id'] = f"product-{i+1}"
            products.append(product)
            logger.info(f"Generated product {i+1}: {product}")
            
        # Store in the inventory
        storage['/product'] = products
        logger.info(f"Pre-populated product inventory with {len(products)} products")
    
    # Initialize the inventory
    initialize_product_inventory()
    
    # Add dynamic routes based on the OpenAPI spec
    paths = openapi_spec.get('paths', {})
    for path, path_item in paths.items():
        for method, operation in path_item.items():
            if method.lower() not in ['get', 'post', 'put', 'delete', 'patch']:
                continue
                
            operation_id = operation.get('operationId', f"{method}_{path}")
            summary = operation.get('summary', '')
            description = operation.get('description', '')
            tags = operation.get('tags', [])
            
            # Find success response schema
            responses = operation.get('responses', {})
            response_schema = None
            for status_code, response in responses.items():
                if status_code.startswith('2'):  # 2xx response
                    content = response.get('content', {})
                    json_content = content.get('application/json', {})
                    response_schema = json_content.get('schema', {})
                    break
            
            # Generate sample response data
            sample_response = generate_sample_data(response_schema) if response_schema else {}
            
            # Define the endpoint handler directly without the nested function
            async def endpoint_handler(request: Request, method=method, path=path, operation_id=operation_id, sample_response=sample_response):
                logger.info(f"{method.upper()} {path} ({operation_id})")
                logger.debug(f"Sample response type: {type(sample_response)}, is_list: {isinstance(sample_response, list)}")
                
                # Simulate network delay if configured
                if delay > 0:
                    await asyncio.sleep(delay)  # Use asyncio.sleep instead of time.sleep
                
                # Extract path parameters
                path_params = request.path_params
                
                # Extract query parameters for filtering and pagination
                query_params = dict(request.query_params)
                
                # For GET requests returning collections
                if method.lower() == 'get' and (isinstance(sample_response, list) or operation_id == 'listProduct'):
                    # Check if we have stored data for this path
                    if path in storage:
                        result = storage[path]
                        
                        # Apply filtering if query parameters are provided
                        if query_params:
                            filtered_result = []
                            for item in result:
                                # Simple filtering based on exact matches
                                match = True
                                for key, value in query_params.items():
                                    # Skip pagination parameters
                                    if key in ['limit', 'offset', 'fields']:
                                        continue
                                        
                                    # Handle nested properties with dot notation (e.g., "status.value")
                                    if '.' in key:
                                        parts = key.split('.')
                                        item_value = item
                                        for part in parts:
                                            if isinstance(item_value, dict) and part in item_value:
                                                item_value = item_value[part]
                                            else:
                                                item_value = None
                                                break
                                        
                                        if str(item_value) != value:
                                            match = False
                                            break
                                    # Handle direct properties
                                    elif key not in item or str(item[key]) != value:
                                        match = False
                                        break
                                
                                if match:
                                    filtered_result.append(item)
                            
                            result = filtered_result
                        
                        # Apply pagination
                        offset = int(query_params.get('offset', 0))
                        limit = int(query_params.get('limit', len(result)))
                        
                        # Apply field selection if specified
                        fields = query_params.get('fields')
                        if fields:
                            field_list = fields.split(',')
                            # Create new list with only selected fields
                            filtered_fields_result = []
                            for item in result[offset:offset+limit]:
                                filtered_item = {}
                                for field in field_list:
                                    if field in item:
                                        filtered_item[field] = item[field]
                                filtered_fields_result.append(filtered_item)
                            return filtered_fields_result
                        
                        return result[offset:offset+limit]
                    else:
                        # Store and return sample data
                        storage[path] = sample_response
                        return sample_response
                
                # For GET requests returning a single item
                elif method.lower() == 'get' and path_params:
                    item_id = next(iter(path_params.values()))
                    collection_path = path.split('/{')[0]
                    
                    if collection_path in storage and isinstance(storage[collection_path], list):
                        # Find the item by ID
                        for item in storage[collection_path]:
                            if item.get('id') == item_id:
                                # Apply field selection if specified
                                fields = query_params.get('fields')
                                if fields:
                                    field_list = fields.split(',')
                                    filtered_item = {}
                                    for field in field_list:
                                        if field in item:
                                            filtered_item[field] = item[field]
                                    return filtered_item
                                return item
                        
                        # If not found, return 404
                        raise HTTPException(status_code=404, detail=f"Item with id {item_id} not found")
                    
                    # If collection doesn't exist, return sample data
                    return sample_response
                
                # For POST requests
                elif method.lower() == 'post':
                    try:
                        body = await request.json()
                        
                        # Generate an ID if not provided
                        if isinstance(body, dict) and 'id' not in body:
                            import uuid
                            body['id'] = str(uuid.uuid4())
                        
                        # Add creation timestamp
                        if isinstance(body, dict):
                            from datetime import datetime
                            if 'creationDate' not in body:
                                body['creationDate'] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                        
                        # Store the item
                        collection_path = path
                        if collection_path not in storage:
                            storage[collection_path] = []
                        
                        storage[collection_path].append(body)
                        
                        # Return 201 Created with the created resource
                        return JSONResponse(status_code=201, content=body)
                    except Exception as e:
                        logger.error(f"Error processing POST request: {e}")
                        raise HTTPException(status_code=400, detail=f"Invalid request: {str(e)}")
                
                # For PUT/PATCH requests
                elif method.lower() in ['put', 'patch'] and path_params:
                    try:
                        body = await request.json()
                        item_id = next(iter(path_params.values()))
                        collection_path = path.split('/{')[0]
                        
                        if collection_path in storage and isinstance(storage[collection_path], list):
                            # Find and update the item
                            for i, item in enumerate(storage[collection_path]):
                                if item.get('id') == item_id:
                                    # Update lastUpdate timestamp
                                    from datetime import datetime
                                    if isinstance(body, dict):
                                        body['lastUpdate'] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                                    
                                    if method.lower() == 'put':
                                        # Preserve the ID in case it's not in the body
                                        if isinstance(body, dict) and 'id' not in body:
                                            body['id'] = item_id
                                        storage[collection_path][i] = body
                                    else:  # PATCH
                                        storage[collection_path][i].update(body)
                                    return storage[collection_path][i]
                            
                            # If not found, return 404
                            raise HTTPException(status_code=404, detail=f"Item with id {item_id} not found")
                        
                        # If collection doesn't exist, return 404
                        raise HTTPException(status_code=404, detail=f"Collection {collection_path} not found")
                    except Exception as e:
                        logger.error(f"Error processing {method.upper()} request: {e}")
                        raise HTTPException(status_code=400, detail=f"Invalid request: {str(e)}")
                
                # For DELETE requests
                elif method.lower() == 'delete' and path_params:
                    item_id = next(iter(path_params.values()))
                    collection_path = path.split('/{')[0]
                    
                    if collection_path in storage and isinstance(storage[collection_path], list):
                        # Find and remove the item
                        for i, item in enumerate(storage[collection_path]):
                            if item.get('id') == item_id:
                                del storage[collection_path][i]
                                return Response(status_code=204)
                        
                        # If not found, return 404
                        raise HTTPException(status_code=404, detail=f"Item with id {item_id} not found")
                    
                    # If collection doesn't exist, return 404
                    raise HTTPException(status_code=404, detail=f"Collection {collection_path} not found")
                
                # Default: return sample data
                return sample_response
            
            # Register the endpoint
            fastapi_path = path.replace('{', '{').replace('}', '}')  # Keep OpenAPI path params as is
            logger.info(f"Registering route: {method.upper()} {fastapi_path} ({operation_id})")
            app.add_api_route(
                path=fastapi_path,
                endpoint=endpoint_handler,
                methods=[method.upper()],
                summary=summary,
                description=description,
                tags=tags,
                operation_id=operation_id
            )
    
    # Add a health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {"status": "healthy", "service": "TMF637 Product Inventory API Mock Server"}
    
    # Add a debug endpoint to view current storage state
    @app.get("/debug/storage", tags=["Debug"])
    async def view_storage():
        """Debug endpoint to view the current in-memory storage state"""
        return storage
        
    # Add a debug endpoint to view all registered routes
    @app.get("/debug/routes", tags=["Debug"])
    async def view_routes():
        """Debug endpoint to view all registered routes"""
        routes = []
        for route in app.routes:
            routes.append({
                "path": route.path,
                "methods": [method for method in route.methods] if hasattr(route, "methods") else [],
                "name": route.name if hasattr(route, "name") else None
            })
        return {"routes": routes}
    
    # Add an endpoint to reset the storage to initial state
    @app.post("/debug/reset", tags=["Debug"])
    async def reset_storage():
        """Reset the in-memory storage to initial state"""
        storage.clear()
        # Re-initialize with sample data
        initialize_product_inventory()
        return {"status": "success", "message": "Storage reset to initial state"}
    
    # Add an endpoint to simulate errors for testing client error handling
    @app.get("/debug/error/{status_code}", tags=["Debug"])
    async def simulate_error(status_code: int = Path(..., description="HTTP status code to simulate")):
        """Simulate an error response with the specified status code"""
        error_messages = {
            400: "Bad Request - The request could not be understood",
            401: "Unauthorized - Authentication is required",
            403: "Forbidden - You don't have permission to access this resource",
            404: "Not Found - The requested resource was not found",
            409: "Conflict - The request could not be completed due to a conflict",
            500: "Internal Server Error - Something went wrong on the server"
        }
        
        message = error_messages.get(status_code, f"Error with status code {status_code}")
        raise HTTPException(status_code=status_code, detail=message)
    
    return app

# Main function to run the server
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="TMF637 Product Inventory API Mock Server")
    parser.add_argument("--spec", default="TMF637-ProductInventory-v5.0.0.oas.yaml", 
                        help="Path to the OpenAPI specification YAML file")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8637, help="Port to bind the server to")
    parser.add_argument("--delay", type=float, default=0, help="Simulated network delay in seconds")
    parser.add_argument("--log-level", default="INFO", 
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Set the logging level")
    parser.add_argument("--persistence", default=None, help="Path to save/load mock data (JSON file)")
    
    args = parser.parse_args()
    
    # Configure logging based on command line argument
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load the OpenAPI specification
    openapi_spec = load_openapi_spec(args.spec)
    
    # Create the FastAPI application
    app = create_mock_api(openapi_spec, args.delay)
    
    # Load persisted data if specified
    if args.persistence and os.path.exists(args.persistence):
        try:
            with open(args.persistence, 'r') as f:
                storage_data = json.load(f)
                # Update the storage dictionary in the app
                for path, data in storage_data.items():
                    app.state.storage[path] = data
            logger.info(f"Loaded persisted data from {args.persistence}")
        except Exception as e:
            logger.error(f"Failed to load persisted data: {e}")
    
    # Add middleware for persistence if specified
    if args.persistence:
        @app.middleware("http")
        async def persistence_middleware(request: Request, call_next):
            # Process the request
            response = await call_next(request)
            
            # After processing, save the current state
            try:
                with open(args.persistence, 'w') as f:
                    json.dump(app.state.storage, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to persist data: {e}")
                
            return response
    
    # Run the server
    print(f"Starting TMF637 Product Inventory API Mock Server...")
    print(f"OpenAPI Spec: {args.spec}")
    print(f"Server: http://{args.host}:{args.port}")
    print(f"Documentation: http://{args.host}:{args.port}/docs")
    print(f"Debug endpoints: http://{args.host}:{args.port}/debug")
    if args.delay > 0:
        print(f"Simulated network delay: {args.delay} seconds")
    if args.persistence:
        print(f"Data persistence enabled: {args.persistence}")
    
    uvicorn.run(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()