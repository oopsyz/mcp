from pprint import pprint
from typing import Any, Optional

from tmf620_core import TMF620Client


def _client() -> TMF620Client:
    return TMF620Client()


def get_catalogs() -> Any:
    """Get all catalogs."""
    return _client().list_catalogs()


def get_catalog(catalog_id: str) -> Any:
    """Get a specific catalog by ID."""
    return _client().get_catalog(catalog_id)


def get_product_offerings(catalog_id: Optional[str] = None) -> Any:
    """Get product offerings, optionally filtered by catalog ID."""
    return _client().list_product_offerings(catalog_id)


def get_product_offering(offering_id: str) -> Any:
    """Get a specific product offering by ID."""
    return _client().get_product_offering(offering_id)


def get_product_specifications() -> Any:
    """Get all product specifications."""
    return _client().list_product_specifications()


def get_product_specification(spec_id: str) -> Any:
    """Get a specific product specification by ID."""
    return _client().get_product_specification(spec_id)


def create_product_offering(name: str, description: str, catalog_id: str) -> Any:
    """Create a new product offering."""
    return _client().create_product_offering(name, description, catalog_id)


def print_catalog_summary() -> None:
    """Print a summary of all catalogs and their offerings."""
    client = _client()
    catalogs = client.list_catalogs()

    print("\n===== TMF620 PRODUCT CATALOG SUMMARY =====\n")

    for catalog in catalogs:
        print(f"CATALOG: {catalog['name']} (ID: {catalog['id']})")
        print(f"Description: {catalog['description']}")
        print(f"Status: {catalog['lifecycleStatus']}")
        print(f"Valid From: {catalog['validFor']['startDateTime']}")
        print(f"Valid To: {catalog['validFor']['endDateTime']}")
        print("\nProduct Offerings:")

        offerings = client.list_product_offerings(catalog["id"])
        if not offerings:
            print("  No offerings in this catalog")

        for offering in offerings:
            print(f"  - {offering['name']}: {offering['description']}")
            spec_ref = offering.get("productSpecification")
            if spec_ref:
                spec = client.get_product_specification(spec_ref["id"])
                print(f"    Specification: {spec['name']}")
                print("    Characteristics:")

                for characteristic in spec.get("productSpecCharacteristic", []):
                    values = characteristic.get("productSpecCharacteristicValue", [])
                    if values:
                        value = values[0].get("value", "N/A")
                        value_str = f"{value}"
                        if "unitOfMeasure" in values[0]:
                            value_str += f" {values[0]['unitOfMeasure']}"
                        print(f"      - {characteristic['name']}: {value_str}")

        print(f"\n{'=' * 50}\n")


if __name__ == "__main__":
    pprint(get_catalogs())
