from flask import Flask, jsonify, request
import json
import uuid
from datetime import datetime, timedelta

app = Flask(__name__)

# Sample data
catalogs = [
    {
        "id": "cat-001",
        "href": "/tmf-api/productCatalogManagement/v4/catalog/cat-001",
        "name": "Enterprise Services Catalog",
        "description": "Catalog containing enterprise-grade telecommunications services",
        "lastUpdate": (datetime.now() - timedelta(days=30)).isoformat(),
        "lifecycleStatus": "Active",
        "validFor": {
            "startDateTime": (datetime.now() - timedelta(days=365)).isoformat(),
            "endDateTime": (datetime.now() + timedelta(days=365)).isoformat()
        },
        "version": "1.0"
    },
    {
        "id": "cat-002",
        "href": "/tmf-api/productCatalogManagement/v4/catalog/cat-002",
        "name": "Consumer Mobile Services",
        "description": "Catalog containing consumer mobile plans and add-ons",
        "lastUpdate": (datetime.now() - timedelta(days=15)).isoformat(),
        "lifecycleStatus": "Active",
        "validFor": {
            "startDateTime": (datetime.now() - timedelta(days=180)).isoformat(),
            "endDateTime": (datetime.now() + timedelta(days=545)).isoformat()
        },
        "version": "2.1"
    }
]

product_offerings = [
    {
        "id": "po-001",
        "href": "/tmf-api/productCatalogManagement/v4/productOffering/po-001",
        "name": "Business Fiber Internet",
        "description": "High-speed fiber internet for businesses with 99.9% uptime SLA",
        "version": "1.0",
        "validFor": {
            "startDateTime": (datetime.now() - timedelta(days=90)).isoformat(),
            "endDateTime": (datetime.now() + timedelta(days=275)).isoformat()
        },
        "lifecycleStatus": "Active",
        "isBundle": False,
        "isSellable": True,
        "catalogId": "cat-001",
        "category": [
            {
                "id": "category-internet",
                "href": "/tmf-api/productCatalogManagement/v4/category/category-internet",
                "name": "Internet Services"
            }
        ],
        "productSpecification": {
            "id": "ps-001",
            "href": "/tmf-api/productCatalogManagement/v4/productSpecification/ps-001",
            "name": "Fiber Internet Specification"
        }
    },
    {
        "id": "po-002",
        "href": "/tmf-api/productCatalogManagement/v4/productOffering/po-002",
        "name": "Unlimited 5G Data Plan",
        "description": "Unlimited 5G data with no throttling for mobile devices",
        "version": "3.1",
        "validFor": {
            "startDateTime": (datetime.now() - timedelta(days=45)).isoformat(),
            "endDateTime": (datetime.now() + timedelta(days=320)).isoformat()
        },
        "lifecycleStatus": "Active",
        "isBundle": False,
        "isSellable": True,
        "catalogId": "cat-002",
        "category": [
            {
                "id": "category-mobile",
                "href": "/tmf-api/productCatalogManagement/v4/category/category-mobile",
                "name": "Mobile Services"
            }
        ],
        "productSpecification": {
            "id": "ps-002",
            "href": "/tmf-api/productCatalogManagement/v4/productSpecification/ps-002",
            "name": "5G Data Plan Specification"
        }
    }
]

product_specifications = [
    {
        "id": "ps-001",
        "href": "/tmf-api/productCatalogManagement/v4/productSpecification/ps-001",
        "name": "Fiber Internet Specification",
        "description": "Technical specification for fiber internet service",
        "version": "1.0",
        "validFor": {
            "startDateTime": (datetime.now() - timedelta(days=120)).isoformat(),
            "endDateTime": (datetime.now() + timedelta(days=245)).isoformat()
        },
        "lifecycleStatus": "Active",
        "productSpecCharacteristic": [
            {
                "name": "Download Speed",
                "description": "Maximum download speed",
                "valueType": "Number",
                "configurable": True,
                "productSpecCharacteristicValue": [
                    {
                        "valueType": "Number",
                        "value": 1000,
                        "unitOfMeasure": "Mbps",
                        "isDefault": True
                    }
                ]
            },
            {
                "name": "Upload Speed",
                "description": "Maximum upload speed",
                "valueType": "Number",
                "configurable": True,
                "productSpecCharacteristicValue": [
                    {
                        "valueType": "Number",
                        "value": 500,
                        "unitOfMeasure": "Mbps",
                        "isDefault": True
                    }
                ]
            }
        ]
    },
    {
        "id": "ps-002",
        "href": "/tmf-api/productCatalogManagement/v4/productSpecification/ps-002",
        "name": "5G Data Plan Specification",
        "description": "Technical specification for 5G unlimited data plan",
        "version": "3.0",
        "validFor": {
            "startDateTime": (datetime.now() - timedelta(days=60)).isoformat(),
            "endDateTime": (datetime.now() + timedelta(days=305)).isoformat()
        },
        "lifecycleStatus": "Active",
        "productSpecCharacteristic": [
            {
                "name": "Data Limit",
                "description": "Monthly data limit",
                "valueType": "String",
                "configurable": False,
                "productSpecCharacteristicValue": [
                    {
                        "valueType": "String",
                        "value": "Unlimited",
                        "isDefault": True
                    }
                ]
            },
            {
                "name": "Network Type",
                "description": "Type of mobile network",
                "valueType": "String",
                "configurable": False,
                "productSpecCharacteristicValue": [
                    {
                        "valueType": "String",
                        "value": "5G",
                        "isDefault": True
                    }
                ]
            }
        ]
    }
]

# API Schema
api_schema = {
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

# API Routes
@app.route('/tmf-api/productCatalogManagement/v4/catalog', methods=['GET'])
def get_catalogs():
    return jsonify(catalogs)

@app.route('/tmf-api/productCatalogManagement/v4/catalog/<catalog_id>', methods=['GET'])
def get_catalog(catalog_id):
    catalog = next((c for c in catalogs if c['id'] == catalog_id), None)
    if catalog:
        return jsonify(catalog)
    return jsonify({"error": "Catalog not found"}), 404

@app.route('/tmf-api/productCatalogManagement/v4/productOffering', methods=['GET'])
def get_product_offerings():
    catalog_id = request.args.get('catalogId')
    if catalog_id:
        filtered_offerings = [po for po in product_offerings if po['catalogId'] == catalog_id]
        return jsonify(filtered_offerings)
    return jsonify(product_offerings)

@app.route('/tmf-api/productCatalogManagement/v4/productOffering/<offering_id>', methods=['GET'])
def get_product_offering(offering_id):
    offering = next((po for po in product_offerings if po['id'] == offering_id), None)
    if offering:
        return jsonify(offering)
    return jsonify({"error": "Product offering not found"}), 404

@app.route('/tmf-api/productCatalogManagement/v4/productSpecification', methods=['GET'])
def get_product_specifications():
    return jsonify(product_specifications)

@app.route('/tmf-api/productCatalogManagement/v4/productSpecification/<spec_id>', methods=['GET'])
def get_product_specification(spec_id):
    spec = next((ps for ps in product_specifications if ps['id'] == spec_id), None)
    if spec:
        return jsonify(spec)
    return jsonify({"error": "Product specification not found"}), 404

@app.route('/tmf-api/productCatalogManagement/v4/productOffering', methods=['POST'])
def create_product_offering():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid data"}), 400
    
    # Generate a new ID if not provided
    if 'id' not in data:
        data['id'] = f"po-{str(uuid.uuid4())[:8]}"
    
    # Add href if not provided
    if 'href' not in data:
        data['href'] = f"/tmf-api/productCatalogManagement/v4/productOffering/{data['id']}"
    
    # Add to product offerings
    product_offerings.append(data)
    return jsonify(data), 201

@app.route('/tmf-api/productCatalogManagement/v4/schema', methods=['GET'])
def get_schema():
    return jsonify(api_schema)

if __name__ == '__main__':
    print("Starting mock TMF620 API server on http://localhost:8000")
    app.run(host='0.0.0.0', port=8000, debug=True) 