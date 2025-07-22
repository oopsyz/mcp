#!/usr/bin/env python3
"""
Startup script for TMF760 Product Configuration API Server
"""

import uvicorn
from tmf760_server import app

if __name__ == "__main__":
    print("Starting TMF760 Product Configuration API Server...")
    print("API Documentation will be available at: http://localhost:8760/docs")
    print("OpenAPI spec will be available at: http://localhost:8760/openapi.json")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8760,
        log_level="info"
    )