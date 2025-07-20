from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
import json
import os
from fastapi_mcp import FastApiMCP

# Load configuration from JSON file
def load_mock_config():
    config_path = os.path.join(os.path.dirname(__file__), 'mock_server_config.json')
    with open(config_path, 'r') as f:
        return json.load(f)

mock_config = load_mock_config()

app = FastAPI(
    title=mock_config['server']['name'],
    description=mock_config['server']['description'],
    version=mock_config['server']['version']
)

# Initialize MCP
mcp = FastApiMCP(app)

# Pydantic Models
class ValidFor(BaseModel):
    startDateTime: datetime
    endDateTime: datetime

class Category(BaseModel):
    id: str
    href: str
    name: str

class ProductSpecificationRef(BaseModel):
    id: str
    href: str
    name: str

class ProductSpecCharacteristicValue(BaseModel):
    valueType: str
    value: Any
    unitOfMeasure: Optional[str] = None
    isDefault: bool = True

class ProductSpecCharacteristic(BaseModel):
    name: str
    description: str
    valueType: str
    configurable: bool
    productSpecCharacteristicValue: List[ProductSpecCharacteristicValue]

class Catalog(BaseModel):
    id: str
    href: str
    name: str
    description: str
    lastUpdate: datetime
    lifecycleStatus: str
    validFor: ValidFor
    version: str

class ProductOffering(BaseModel):
    id: str
    href: str
    name: str
    description: str
    version: str
    validFor: ValidFor
    lifecycleStatus: str
    isBundle: bool
    isSellable: bool
    catalogId: str
    category: List[Category]
    productSpecification: ProductSpecificationRef

class ProductSpecification(BaseModel):
    id: str
    href: str
    name: str
    description: str
    version: str
    validFor: ValidFor
    lifecycleStatus: str
    productSpecCharacteristic: List[ProductSpecCharacteristic]

# Sample data
catalogs = [
    Catalog(
        id="cat-001",
        href="/tmf-api/productCatalogManagement/v4/catalog/cat-001",
        name="Enterprise Services Catalog",
        description="Catalog containing enterprise-grade telecommunications services",
        lastUpdate=datetime.now() - timedelta(days=30),
        lifecycleStatus="Active",
        validFor=ValidFor(
            startDateTime=datetime.now() - timedelta(days=365),
            endDateTime=datetime.now() + timedelta(days=365)
        ),
        version="1.0"
    ),
    Catalog(
        id="cat-002",
        href="/tmf-api/productCatalogManagement/v4/catalog/cat-002",
        name="Consumer Mobile Services",
        description="Catalog containing consumer mobile plans and add-ons",
        lastUpdate=datetime.now() - timedelta(days=15),
        lifecycleStatus="Active",
        validFor=ValidFor(
            startDateTime=datetime.now() - timedelta(days=180),
            endDateTime=datetime.now() + timedelta(days=545)
        ),
        version="2.1"
    )
]

product_offerings = [
    ProductOffering(
        id="po-001",
        href="/tmf-api/productCatalogManagement/v4/productOffering/po-001",
        name="Business Fiber Internet",
        description="High-speed fiber internet for businesses with 99.9% uptime SLA",
        version="1.0",
        validFor=ValidFor(
            startDateTime=datetime.now() - timedelta(days=90),
            endDateTime=datetime.now() + timedelta(days=275)
        ),
        lifecycleStatus="Active",
        isBundle=False,
        isSellable=True,
        catalogId="cat-001",
        category=[
            Category(
                id="category-internet",
                href="/tmf-api/productCatalogManagement/v4/category/category-internet",
                name="Internet Services"
            )
        ],
        productSpecification=ProductSpecificationRef(
            id="ps-001",
            href="/tmf-api/productCatalogManagement/v4/productSpecification/ps-001",
            name="Fiber Internet Specification"
        )
    ),
    ProductOffering(
        id="po-002",
        href="/tmf-api/productCatalogManagement/v4/productOffering/po-002",
        name="Unlimited 5G Data Plan",
        description="Unlimited 5G data with no throttling for mobile devices",
        version="3.1",
        validFor=ValidFor(
            startDateTime=datetime.now() - timedelta(days=45),
            endDateTime=datetime.now() + timedelta(days=320)
        ),
        lifecycleStatus="Active",
        isBundle=False,
        isSellable=True,
        catalogId="cat-002",
        category=[
            Category(
                id="category-mobile",
                href="/tmf-api/productCatalogManagement/v4/category/category-mobile",
                name="Mobile Services"
            )
        ],
        productSpecification=ProductSpecificationRef(
            id="ps-002",
            href="/tmf-api/productCatalogManagement/v4/productSpecification/ps-002",
            name="5G Data Plan Specification"
        )
    )
]

product_specifications = [
    ProductSpecification(
        id="ps-001",
        href="/tmf-api/productCatalogManagement/v4/productSpecification/ps-001",
        name="Fiber Internet Specification",
        description="Technical specification for fiber internet service",
        version="1.0",
        validFor=ValidFor(
            startDateTime=datetime.now() - timedelta(days=120),
            endDateTime=datetime.now() + timedelta(days=245)
        ),
        lifecycleStatus="Active",
        productSpecCharacteristic=[
            ProductSpecCharacteristic(
                name="Download Speed",
                description="Maximum download speed",
                valueType="Number",
                configurable=True,
                productSpecCharacteristicValue=[
                    ProductSpecCharacteristicValue(
                        valueType="Number",
                        value=1000,
                        unitOfMeasure="Mbps",
                        isDefault=True
                    )
                ]
            ),
            ProductSpecCharacteristic(
                name="Upload Speed",
                description="Maximum upload speed",
                valueType="Number",
                configurable=True,
                productSpecCharacteristicValue=[
                    ProductSpecCharacteristicValue(
                        valueType="Number",
                        value=500,
                        unitOfMeasure="Mbps",
                        isDefault=True
                    )
                ]
            )
        ]
    ),
    ProductSpecification(
        id="ps-002",
        href="/tmf-api/productCatalogManagement/v4/productSpecification/ps-002",
        name="5G Data Plan Specification",
        description="Technical specification for 5G unlimited data plan",
        version="3.0",
        validFor=ValidFor(
            startDateTime=datetime.now() - timedelta(days=60),
            endDateTime=datetime.now() + timedelta(days=305)
        ),
        lifecycleStatus="Active",
        productSpecCharacteristic=[
            ProductSpecCharacteristic(
                name="Data Limit",
                description="Monthly data limit",
                valueType="String",
                configurable=False,
                productSpecCharacteristicValue=[
                    ProductSpecCharacteristicValue(
                        valueType="String",
                        value="Unlimited",
                        isDefault=True
                    )
                ]
            ),
            ProductSpecCharacteristic(
                name="Network Type",
                description="Type of mobile network",
                valueType="String",
                configurable=False,
                productSpecCharacteristicValue=[
                    ProductSpecCharacteristicValue(
                        valueType="String",
                        value="5G",
                        isDefault=True
                    )
                ]
            )
        ]
    )
]

# API Routes
@app.get(
    "/tmf-api/productCatalogManagement/v4/catalog",
    response_model=List[Catalog],
    summary="List all catalogs",
    description="Retrieves a list of all available product catalogs. Each catalog contains a collection of product offerings."
)
async def get_catalogs():
    return catalogs

@app.get(
    "/tmf-api/productCatalogManagement/v4/catalog/{catalog_id}",
    response_model=Catalog,
    summary="Get catalog by ID",
    description="Retrieves detailed information about a specific catalog using its unique identifier."
)
async def get_catalog(catalog_id: str):
    catalog = next((c for c in catalogs if c.id == catalog_id), None)
    if not catalog:
        raise HTTPException(status_code=404, detail="Catalog not found")
    return catalog

@app.get(
    "/tmf-api/productCatalogManagement/v4/productOffering",
    response_model=List[ProductOffering],
    summary="List product offerings",
    description="Retrieves a list of all product offerings. Can be filtered by catalog ID using the catalog_id query parameter."
)
async def get_product_offerings(catalog_id: Optional[str] = Query(None, description="Filter offerings by catalog ID")):
    if catalog_id:
        return [po for po in product_offerings if po.catalogId == catalog_id]
    return product_offerings

@app.get(
    "/tmf-api/productCatalogManagement/v4/productOffering/{offering_id}",
    response_model=ProductOffering,
    summary="Get product offering by ID",
    description="Retrieves detailed information about a specific product offering using its unique identifier."
)
async def get_product_offering(offering_id: str):
    offering = next((po for po in product_offerings if po.id == offering_id), None)
    if not offering:
        raise HTTPException(status_code=404, detail="Product offering not found")
    return offering

@app.get(
    "/tmf-api/productCatalogManagement/v4/productSpecification",
    response_model=List[ProductSpecification],
    summary="List product specifications",
    description="Retrieves a list of all product specifications. These define the technical characteristics of product offerings."
)
async def get_product_specifications():
    return product_specifications

@app.get(
    "/tmf-api/productCatalogManagement/v4/productSpecification/{spec_id}",
    response_model=ProductSpecification,
    summary="Get product specification by ID",
    description="Retrieves detailed technical specifications for a specific product using its unique identifier."
)
async def get_product_specification(spec_id: str):
    spec = next((ps for ps in product_specifications if ps.id == spec_id), None)
    if not spec:
        raise HTTPException(status_code=404, detail="Product specification not found")
    return spec

@app.post(
    "/tmf-api/productCatalogManagement/v4/productOffering",
    response_model=ProductOffering,
    status_code=201,
    summary="Create new product offering",
    description="Creates a new product offering. If no ID is provided, one will be generated automatically."
)
async def create_product_offering(offering: ProductOffering):
    if not offering.id:
        offering.id = f"po-{str(uuid.uuid4())[:8]}"
    if not offering.href:
        offering.href = f"/tmf-api/productCatalogManagement/v4/productOffering/{offering.id}"
    product_offerings.append(offering)
    return offering

@app.get("/tmf-api/productCatalogManagement/v4/schema")
async def get_schema():
    return {
        "swagger": "2.0",
        "info": {
            "description": "TMF620 Product Catalog Management API",
            "version": "4.0.0",
            "title": "TMF620 Product Catalog Management"
        },
        "basePath": "/tmf-api/productCatalogManagement/v4",
        "paths": {
            "/catalog": {
                "get": {
                    "description": "List all catalogs",
                    "responses": {
                        "200": {
                            "description": "Success"
                        }
                    }
                }
            },
            "/catalog/{id}": {
                "get": {
                    "description": "Get catalog by ID",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "type": "string"
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Success"
                        }
                    }
                }
            }
        }
    }

def main():
    """Main entry point for the mock TMF620 API server"""
    import uvicorn
    # Mount MCP server
    if mock_config['features']['enable_mcp']:
        mcp.mount()
    
    server_config = mock_config['server']
    print(f"Starting {server_config['name']} on {server_config['protocol']}://{server_config['host']}:{server_config['port']}")
    if mock_config['features']['enable_mcp']:
        print(f"MCP server available at {server_config['protocol']}://{server_config['host']}:{server_config['port']}/mcp")
    if mock_config['features']['enable_docs']:
        print(f"API Documentation available at {server_config['protocol']}://{server_config['host']}:{server_config['port']}/docs")
    
    uvicorn.run(app, host=server_config['host'], port=server_config['port'])

if __name__ == "__main__":
    main() 