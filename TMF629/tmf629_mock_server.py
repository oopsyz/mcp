
#!/usr/bin/env python3
"""
TMF629 Mock Server
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
logger = logging.getLogger("tmf-mock-server")

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

def generate_sample_data(schema: Dict[str, Any]) -> Any:
    """Generate sample data based on an OpenAPI schema"""
    if 'type' not in schema:
        return {}
    
    schema_type = schema['type']
    
    if schema_type == 'object':
        result = {}
        for prop_name, prop_schema in schema.get('properties', {}).items():
            result[prop_name] = generate_sample_data(prop_schema)
        return result
    
    elif schema_type == 'array':
        items_schema = schema.get('items', {})
        return [generate_sample_data(items_schema) for _ in range(2)]  # Generate 2 sample items
    
    elif schema_type == 'string':
        if schema.get('format') == 'date-time':
            return "2023-01-01T00:00:00Z"
        elif schema.get('format') == 'date':
            return "2023-01-01"
        elif schema.get('format') == 'uri':
            return "http://example.com/resource"
        elif schema.get('format') == 'email':
            return "user@example.com"
        elif 'enum' in schema:
            return schema['enum'][0]  # Return first enum value
        else:
            return "sample-string"
    
    elif schema_type == 'number' or schema_type == 'integer':
        return 42
    
    elif schema_type == 'boolean':
        return True
    
    else:
        return None

def create_mock_api(openapi_spec: Dict[str, Any], delay: float = 0) -> FastAPI:
    """Create a FastAPI application based on the OpenAPI specification"""
    info = openapi_spec.get('info', {})
    app = FastAPI(
        title=info.get('title', 'TMF API Mock Server'),
        description=info.get('description', 'Mock implementation of TMF API'),
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
            
            # Define the endpoint handler directly without nested functions
            async def endpoint_handler(request: Request, method=method, path=path, operation_id=operation_id, sample_response=sample_response):
                logger.info(f"{method.upper()} {path} ({operation_id})")
                
                # Simulate network delay if configured
                if delay > 0:
                    await asyncio.sleep(delay)  # Use asyncio.sleep instead of time.sleep
                    
                    # Extract path parameters
                    path_params = request.path_params
                    
                    # For GET requests returning collections
                    if method.lower() == 'get' and isinstance(sample_response, list):
                        # Check if we have stored data for this path
                        if path in storage:
                            return storage[path]
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
                                    return item
                        
                        # If not found, return sample data
                        return sample_response
                    
                    # For POST requests
                    elif method.lower() == 'post':
                        try:
                            body = await request.json()
                            
                            # Generate an ID if not provided
                            if isinstance(body, dict) and 'id' not in body:
                                body['id'] = f"id-{len(storage.get(path, []))}"
                            
                            # Store the item
                            collection_path = path
                            if collection_path not in storage:
                                storage[collection_path] = []
                            
                            storage[collection_path].append(body)
                            return body
                        except Exception as e:
                            logger.error(f"Error processing POST request: {e}")
                            return sample_response
                    
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
                                        if method.lower() == 'put':
                                            storage[collection_path][i] = body
                                        else:  # PATCH
                                            storage[collection_path][i].update(body)
                                        return storage[collection_path][i]
                            
                            # If not found, return sample data
                            return sample_response
                        except Exception as e:
                            logger.error(f"Error processing {method.upper()} request: {e}")
                            return sample_response
                    
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
                        
                        # If not found, still return success
                        return Response(status_code=204)
                    
                # Default: return sample data
                return sample_response
            
            # Register the endpoint directly
            app.add_api_route(
                path=path.replace('{', ':').replace('}', ''),  # Convert OpenAPI path params to FastAPI format
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
        return {"status": "healthy", "service": "TMF API Mock Server"}
    
    return app

# Main function to run the server
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="TMF API Mock Server")
    parser.add_argument("--spec", default="TMF629-Customer_Management-v5.0.1.oas.yaml", help="Path to the OpenAPI specification YAML file")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind the server to")
    parser.add_argument("--delay", type=float, default=0, help="Simulated network delay in seconds")
    
    args = parser.parse_args()
    
    # Load the OpenAPI specification
    openapi_spec = load_openapi_spec(args.spec)
    
    # Create the FastAPI application
    app = create_mock_api(openapi_spec, args.delay)
    
    # Run the server
    print(f"Starting TMF API Mock Server...")
    print(f"OpenAPI Spec: {args.spec}")
    print(f"Server: http://{args.host}:{args.port}")
    print(f"Documentation: http://{args.host}:{args.port}/docs")
    if args.delay > 0:
        print(f"Simulated network delay: {args.delay} seconds")
    
    uvicorn.run(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()
