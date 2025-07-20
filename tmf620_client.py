import requests
import json
import os
from pprint import pprint

# Load configuration from JSON file
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r') as f:
        return json.load(f)

config = load_config()

# Base URL for the mock TMF620 API
BASE_URL = config['tmf620_api']['url']

def get_catalogs():
    """Get all catalogs"""
    response = requests.get(f"{BASE_URL}/catalog")
    return response.json()

def get_catalog(catalog_id):
    """Get a specific catalog by ID"""
    response = requests.get(f"{BASE_URL}/catalog/{catalog_id}")
    return response.json()

def get_product_offerings(catalog_id=None):
    """Get product offerings, optionally filtered by catalog ID"""
    url = f"{BASE_URL}/productOffering"
    if catalog_id:
        url += f"?catalogId={catalog_id}"
    response = requests.get(url)
    return response.json()

def get_product_offering(offering_id):
    """Get a specific product offering by ID"""
    response = requests.get(f"{BASE_URL}/productOffering/{offering_id}")
    return response.json()

def get_product_specifications():
    """Get all product specifications"""
    response = requests.get(f"{BASE_URL}/productSpecification")
    return response.json()

def get_product_specification(spec_id):
    """Get a specific product specification by ID"""
    response = requests.get(f"{BASE_URL}/productSpecification/{spec_id}")
    return response.json()

def create_product_offering(name, description, catalog_id):
    """Create a new product offering"""
    data = {
        "name": name,
        "description": description,
        "catalogId": catalog_id,
        "lifecycleStatus": "Active",
        "isBundle": False,
        "isSellable": True
    }
    response = requests.post(f"{BASE_URL}/productOffering", json=data)
    return response.json()

def print_catalog_summary():
    """Print a summary of all catalogs and their offerings"""
    catalogs = get_catalogs()
    
    print("\n===== TMF620 PRODUCT CATALOG SUMMARY =====\n")
    
    for catalog in catalogs:
        print(f"CATALOG: {catalog['name']} (ID: {catalog['id']})")
        print(f"Description: {catalog['description']}")
        print(f"Status: {catalog['lifecycleStatus']}")
        print(f"Valid From: {catalog['validFor']['startDateTime']}")
        print(f"Valid To: {catalog['validFor']['endDateTime']}")
        print("\nProduct Offerings:")
        
        offerings = get_product_offerings(catalog['id'])
        
        if not offerings:
            print("  No offerings in this catalog")
        
        for offering in offerings:
            print(f"  - {offering['name']}: {offering['description']}")
            
            # If the offering has a product specification, get its details
            if 'productSpecification' in offering and offering['productSpecification']:
                spec_id = offering['productSpecification']['id']
                spec = get_product_specification(spec_id)
                
                print(f"    Specification: {spec['name']}")
                print(f"    Characteristics:")
                
                for char in spec.get('productSpecCharacteristic', []):
                    values = char.get('productSpecCharacteristicValue', [])
                    if values:
                        value_str = f"{values[0].get('value', 'N/A')}"
                        if 'unitOfMeasure' in values[0]:
                            value_str += f" {values[0]['unitOfMeasure']}"
                        print(f"      - {char['name']}: {value_str}")
        
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    print_catalog_summary() 