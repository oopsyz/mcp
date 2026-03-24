import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, List, Optional

from fastapi import FastAPI, HTTPException, Query, Response, status
from fastapi_mcp import FastApiMCP
from pydantic import BaseModel, ConfigDict, Field


def load_mock_config() -> dict[str, Any]:
    config_path = os.path.join(os.path.dirname(__file__), "mock_server_config.json")
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    return config


mock_config = load_mock_config()

app = FastAPI(
    title=mock_config["server"]["name"],
    description=mock_config["server"]["description"],
    version=mock_config["server"]["version"],
)
mcp = FastApiMCP(app)

BASE_PATH = "/tmf-api/productCatalogManagement/v5"


class TMFModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class Extensible(TMFModel):
    base_type: Optional[str] = Field(default=None, alias="@baseType")
    schema_location: Optional[str] = Field(default=None, alias="@schemaLocation")
    type_name: Optional[str] = Field(default=None, alias="@type")


class Addressable(TMFModel):
    id: Optional[str] = None
    href: Optional[str] = None


class Entity(Extensible, Addressable):
    pass


class EntityRef(Extensible, Addressable):
    name: Optional[str] = None
    referred_type: Optional[str] = Field(default=None, alias="@referredType")


class ValidFor(TMFModel):
    startDateTime: datetime
    endDateTime: datetime


class Category(Entity):
    name: str
    description: str = ""
    lifecycleStatus: str = "Active"
    isRoot: Optional[bool] = None
    version: Optional[str] = None
    validFor: Optional[ValidFor] = None


class ProductSpecificationRef(EntityRef):
    name: str


class ProductSpecCharacteristicValue(TMFModel):
    valueType: str
    value: Any
    unitOfMeasure: Optional[str] = None
    isDefault: bool = True


class ProductSpecCharacteristic(Extensible):
    name: str
    description: str
    valueType: str
    configurable: bool
    productSpecCharacteristicValue: List[ProductSpecCharacteristicValue]


class Catalog(Entity):
    name: str
    description: str
    lastUpdate: datetime
    lifecycleStatus: str
    validFor: ValidFor
    version: str
    catalogType: Optional[str] = None
    category: list[EntityRef] = []


class ProductOffering(Entity):
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


class Quantity(TMFModel):
    amount: Optional[float] = None
    units: Optional[str] = None


class Money(TMFModel):
    unit: str
    value: float


class ProductOfferingPrice(Entity):
    name: str
    description: str
    version: str
    lifecycleStatus: str
    priceType: str
    lastUpdate: datetime
    price: Money
    validFor: Optional[ValidFor] = None
    unitOfMeasure: Optional[Quantity] = None
    recurringChargePeriodType: Optional[str] = None
    recurringChargePeriodLength: Optional[int] = None
    isBundle: Optional[bool] = None


class ProductSpecification(Entity):
    name: str
    description: str
    version: str
    validFor: ValidFor
    lifecycleStatus: str
    productSpecCharacteristic: List[ProductSpecCharacteristic]
    brand: Optional[str] = None


class ImportJob(Entity):
    contentType: str
    creationDate: datetime
    path: str
    status: str
    url: str
    errorLog: Optional[str] = None


class ExportJob(Entity):
    contentType: str
    creationDate: datetime
    path: str
    query: str
    status: str
    url: str
    errorLog: Optional[str] = None


class Hub(Entity):
    callback: str
    query: Optional[str] = None


class CategoryRef(EntityRef):
    pass


class CategoryRefFVO(EntityRef):
    id: str


class CategoryRefMVO(EntityRef):
    pass


class ProductCatalogFVO(Extensible):
    name: str
    description: Optional[str] = None
    catalogType: Optional[str] = None
    validFor: Optional[ValidFor] = None
    version: Optional[str] = None
    lastUpdate: Optional[datetime] = None
    lifecycleStatus: Optional[str] = None
    category: list[CategoryRefFVO] = []
    type_name: str = Field(alias="@type")


class ProductCatalogMVO(Extensible):
    name: Optional[str] = None
    description: Optional[str] = None
    catalogType: Optional[str] = None
    validFor: Optional[ValidFor] = None
    version: Optional[str] = None
    lifecycleStatus: Optional[str] = None
    category: Optional[list[CategoryRefMVO]] = None


class CategoryFVO(Extensible):
    name: str
    description: Optional[str] = None
    isRoot: Optional[bool] = None
    parent: Optional[CategoryRefFVO] = None
    validFor: Optional[ValidFor] = None
    version: Optional[str] = None
    lastUpdate: Optional[datetime] = None
    lifecycleStatus: Optional[str] = None
    type_name: str = Field(alias="@type")


class CategoryMVO(Extensible):
    name: Optional[str] = None
    description: Optional[str] = None
    isRoot: Optional[bool] = None
    parent: Optional[CategoryRefMVO] = None
    validFor: Optional[ValidFor] = None
    version: Optional[str] = None
    lifecycleStatus: Optional[str] = None


class ProductSpecificationRefFVO(EntityRef):
    id: str
    name: Optional[str] = None


class ProductSpecificationRefMVO(EntityRef):
    pass


class ProductOfferingFVO(Extensible):
    name: str
    description: Optional[str] = None
    isBundle: Optional[bool] = None
    isSellable: Optional[bool] = None
    validFor: Optional[ValidFor] = None
    version: Optional[str] = None
    category: list[CategoryRefFVO] = []
    productSpecification: Optional[ProductSpecificationRefFVO] = None
    lastUpdate: datetime
    lifecycleStatus: str
    type_name: str = Field(alias="@type")


class ProductOfferingMVO(Extensible):
    name: Optional[str] = None
    description: Optional[str] = None
    isBundle: Optional[bool] = None
    isSellable: Optional[bool] = None
    validFor: Optional[ValidFor] = None
    version: Optional[str] = None
    category: Optional[list[CategoryRefMVO]] = None
    productSpecification: Optional[ProductSpecificationRefMVO] = None
    lifecycleStatus: Optional[str] = None


class ProductOfferingPriceFVO(Extensible):
    name: str
    description: Optional[str] = None
    version: Optional[str] = None
    validFor: Optional[ValidFor] = None
    unitOfMeasure: Optional[Quantity] = None
    recurringChargePeriodType: Optional[str] = None
    recurringChargePeriodLength: Optional[int] = None
    isBundle: Optional[bool] = None
    price: Optional[Money] = None
    priceType: str
    lastUpdate: datetime
    lifecycleStatus: str
    type_name: str = Field(alias="@type")


class ProductOfferingPriceMVO(Extensible):
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    validFor: Optional[ValidFor] = None
    unitOfMeasure: Optional[Quantity] = None
    recurringChargePeriodType: Optional[str] = None
    recurringChargePeriodLength: Optional[int] = None
    isBundle: Optional[bool] = None
    price: Optional[Money] = None
    priceType: Optional[str] = None
    lifecycleStatus: Optional[str] = None


class ProductSpecificationFVO(Extensible):
    name: str
    description: Optional[str] = None
    brand: Optional[str] = None
    validFor: Optional[ValidFor] = None
    version: Optional[str] = None
    productSpecCharacteristic: list[ProductSpecCharacteristic] = []
    lastUpdate: datetime
    lifecycleStatus: str
    type_name: str = Field(alias="@type")


class ProductSpecificationMVO(Extensible):
    name: Optional[str] = None
    description: Optional[str] = None
    brand: Optional[str] = None
    validFor: Optional[ValidFor] = None
    version: Optional[str] = None
    productSpecCharacteristic: Optional[list[ProductSpecCharacteristic]] = None
    lifecycleStatus: Optional[str] = None


class HubFVO(Extensible):
    callback: str
    query: Optional[str] = None


def _new_valid_for() -> ValidFor:
    return ValidFor(
        startDateTime=datetime.now(),
        endDateTime=datetime.now() + timedelta(days=365),
    )


categories = [
    Category(
        id="category-internet",
        href=f"{BASE_PATH}/category/category-internet",
        name="Internet Services",
        description="Fixed and business internet services",
        validFor=_new_valid_for(),
        version="1.0",
        isRoot=True,
        type_name="Category",
    ),
    Category(
        id="category-mobile",
        href=f"{BASE_PATH}/category/category-mobile",
        name="Mobile Services",
        description="Consumer mobile services and plans",
        validFor=_new_valid_for(),
        version="1.0",
        isRoot=True,
        type_name="Category",
    ),
]

catalogs = [
    Catalog(
        id="cat-001",
        href=f"{BASE_PATH}/productCatalog/cat-001",
        name="Enterprise Services Catalog",
        description="Catalog containing enterprise-grade telecommunications services",
        lastUpdate=datetime.now() - timedelta(days=30),
        lifecycleStatus="Active",
        validFor=ValidFor(
            startDateTime=datetime.now() - timedelta(days=365),
            endDateTime=datetime.now() + timedelta(days=365),
        ),
        version="1.0",
        catalogType="ProductCatalog",
        category=[
            EntityRef(
                id="category-internet",
                href=f"{BASE_PATH}/category/category-internet",
                name="Internet Services",
                referred_type="Category",
                type_name="CategoryRef",
            )
        ],
        type_name="ProductCatalog",
    ),
    Catalog(
        id="cat-002",
        href=f"{BASE_PATH}/productCatalog/cat-002",
        name="Consumer Mobile Services",
        description="Catalog containing consumer mobile plans and add-ons",
        lastUpdate=datetime.now() - timedelta(days=15),
        lifecycleStatus="Active",
        validFor=ValidFor(
            startDateTime=datetime.now() - timedelta(days=180),
            endDateTime=datetime.now() + timedelta(days=545),
        ),
        version="2.1",
        catalogType="ProductCatalog",
        category=[
            EntityRef(
                id="category-mobile",
                href=f"{BASE_PATH}/category/category-mobile",
                name="Mobile Services",
                referred_type="Category",
                type_name="CategoryRef",
            )
        ],
        type_name="ProductCatalog",
    ),
]

product_specifications = [
    ProductSpecification(
        id="ps-001",
        href=f"{BASE_PATH}/productSpecification/ps-001",
        name="Fiber Internet Specification",
        description="Technical specification for fiber internet service",
        version="1.0",
        validFor=ValidFor(
            startDateTime=datetime.now() - timedelta(days=120),
            endDateTime=datetime.now() + timedelta(days=245),
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
                        isDefault=True,
                    )
                ],
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
                        isDefault=True,
                    )
                ],
            ),
        ],
        type_name="ProductSpecification",
    ),
    ProductSpecification(
        id="ps-002",
        href=f"{BASE_PATH}/productSpecification/ps-002",
        name="5G Data Plan Specification",
        description="Technical specification for 5G unlimited data plan",
        version="3.0",
        validFor=ValidFor(
            startDateTime=datetime.now() - timedelta(days=60),
            endDateTime=datetime.now() + timedelta(days=305),
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
                        isDefault=True,
                    )
                ],
            ),
            ProductSpecCharacteristic(
                name="Network Type",
                description="Type of mobile network",
                valueType="String",
                configurable=False,
                productSpecCharacteristicValue=[
                    ProductSpecCharacteristicValue(
                        valueType="String", value="5G", isDefault=True
                    )
                ],
            ),
        ],
        type_name="ProductSpecification",
    ),
]

product_offerings = [
    ProductOffering(
        id="po-001",
        href=f"{BASE_PATH}/productOffering/po-001",
        name="Business Fiber Internet",
        description="High-speed fiber internet for businesses with 99.9% uptime SLA",
        version="1.0",
        validFor=ValidFor(
            startDateTime=datetime.now() - timedelta(days=90),
            endDateTime=datetime.now() + timedelta(days=275),
        ),
        lifecycleStatus="Active",
        isBundle=False,
        isSellable=True,
        catalogId="cat-001",
        category=[categories[0]],
        productSpecification=ProductSpecificationRef(
            id="ps-001",
            href=f"{BASE_PATH}/productSpecification/ps-001",
            name="Fiber Internet Specification",
            referred_type="ProductSpecification",
            type_name="ProductSpecificationRef",
        ),
        type_name="ProductOffering",
    ),
    ProductOffering(
        id="po-002",
        href=f"{BASE_PATH}/productOffering/po-002",
        name="Unlimited 5G Data Plan",
        description="Unlimited 5G data with no throttling for mobile devices",
        version="3.1",
        validFor=ValidFor(
            startDateTime=datetime.now() - timedelta(days=45),
            endDateTime=datetime.now() + timedelta(days=320),
        ),
        lifecycleStatus="Active",
        isBundle=False,
        isSellable=True,
        catalogId="cat-002",
        category=[categories[1]],
        productSpecification=ProductSpecificationRef(
            id="ps-002",
            href=f"{BASE_PATH}/productSpecification/ps-002",
            name="5G Data Plan Specification",
            referred_type="ProductSpecification",
            type_name="ProductSpecificationRef",
        ),
        type_name="ProductOffering",
    ),
]

product_offering_prices = [
    ProductOfferingPrice(
        id="pop-001",
        href=f"{BASE_PATH}/productOfferingPrice/pop-001",
        name="Business Fiber Monthly",
        description="Monthly recurring charge for business fiber",
        version="1.0",
        lifecycleStatus="Active",
        priceType="recurring",
        lastUpdate=datetime.now() - timedelta(days=10),
        price=Money(unit="USD", value=199.0),
        unitOfMeasure=Quantity(amount=1, units="service"),
        recurringChargePeriodType="month",
        recurringChargePeriodLength=1,
        type_name="ProductOfferingPrice",
    )
]

import_jobs = [
    ImportJob(
        id="import-001",
        href=f"{BASE_PATH}/importJob/import-001",
        contentType="application/json",
        creationDate=datetime.now() - timedelta(days=1),
        path=BASE_PATH,
        status="Succeeded",
        url="ftp://example.com/import-001.json",
        type_name="ImportJob",
    )
]

export_jobs = [
    ExportJob(
        id="export-001",
        href=f"{BASE_PATH}/exportJob/export-001",
        contentType="application/json",
        creationDate=datetime.now() - timedelta(days=1),
        path=f"{BASE_PATH}/productOffering",
        query="catalog.id=cat-001",
        status="Succeeded",
        url="ftp://example.com/export-001.json",
        type_name="ExportJob",
    )
]

hubs = [
    Hub(
        id="hub-001",
        callback="http://localhost:9999/hook",
        query="eventType=ProductOfferingCreateEvent",
        type_name="Hub",
    )
]


def _filter_and_page(
    items: List[Any],
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    lifecycle_status: Optional[str] = None,
) -> List[Any]:
    filtered = items
    if lifecycle_status:
        filtered = [
            item
            for item in filtered
            if getattr(item, "lifecycleStatus", None) == lifecycle_status
        ]

    start = offset or 0
    if limit is None:
        return filtered[start:]
    return filtered[start : start + limit]


def _get_or_404(items: list[Any], item_id: str, label: str) -> Any:
    item = next((entry for entry in items if entry.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return item


def _patch_model(model: BaseModel, payload: dict[str, Any]) -> BaseModel:
    return model.model_copy(update=payload)


def _model_payload(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(by_alias=True, exclude_none=True)


def _render_payload(payload: Any, fields: Optional[str] = None) -> Any:
    def normalize(item: Any) -> Any:
        if isinstance(item, BaseModel):
            return item.model_dump(by_alias=True, exclude_none=True)
        return item

    normalized = normalize(payload)
    if not fields:
        return normalized

    wanted = {field.strip() for field in fields.split(",") if field.strip()}
    if not wanted:
        return normalized

    def project(item: Any) -> Any:
        record = normalize(item)
        if isinstance(record, list):
            return [project(entry) for entry in record]
        if not isinstance(record, dict):
            return record
        keep = {"id", "href", "@type"}
        return {key: value for key, value in record.items() if key in wanted or key in keep}

    return project(normalized)


@app.get(f"{BASE_PATH}/productCatalog")
async def list_product_catalogs(
    fields: Optional[str] = Query(None),
    limit: Optional[int] = Query(None, ge=0),
    offset: Optional[int] = Query(None, ge=0),
    lifecycle_status: Optional[str] = Query(None, alias="lifecycleStatus"),
):
    return _render_payload(
        _filter_and_page(catalogs, limit, offset, lifecycle_status), fields
    )


@app.post(f"{BASE_PATH}/productCatalog", status_code=201)
async def create_product_catalog(
    payload: ProductCatalogFVO, fields: Optional[str] = Query(None)
):
    payload_data = _model_payload(payload)
    catalog_id = payload_data.get("id") or f"cat-{str(uuid.uuid4())[:8]}"
    created = Catalog(
        id=catalog_id,
        href=f"{BASE_PATH}/productCatalog/{catalog_id}",
        name=payload_data["name"],
        description=payload_data.get("description", ""),
        lastUpdate=payload_data.get("lastUpdate") or datetime.now(),
        lifecycleStatus=payload_data.get("lifecycleStatus", "Active"),
        validFor=payload_data.get("validFor") or _new_valid_for(),
        version=payload_data.get("version", "1.0"),
        catalogType=payload_data.get("catalogType", "ProductCatalog"),
        category=payload_data.get("category", []),
        base_type=payload_data.get("@baseType"),
        schema_location=payload_data.get("@schemaLocation"),
        type_name=payload_data["@type"],
    )
    catalogs.append(created)
    return _render_payload(created, fields)


@app.get(f"{BASE_PATH}/productCatalog/{{catalog_id}}")
async def get_product_catalog(catalog_id: str, fields: Optional[str] = Query(None)):
    return _render_payload(_get_or_404(catalogs, catalog_id, "Catalog"), fields)


@app.patch(f"{BASE_PATH}/productCatalog/{{catalog_id}}")
async def patch_product_catalog(
    catalog_id: str, payload: ProductCatalogMVO, fields: Optional[str] = Query(None)
):
    catalog = _get_or_404(catalogs, catalog_id, "Catalog")
    updated = _patch_model(catalog, {**_model_payload(payload), "lastUpdate": datetime.now()})
    catalogs[catalogs.index(catalog)] = updated
    return _render_payload(updated, fields)


@app.delete(f"{BASE_PATH}/productCatalog/{{catalog_id}}", status_code=204)
async def delete_product_catalog(catalog_id: str):
    catalog = _get_or_404(catalogs, catalog_id, "Catalog")
    catalogs.remove(catalog)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get(f"{BASE_PATH}/category")
async def get_categories(
    fields: Optional[str] = Query(None),
    limit: Optional[int] = Query(None, ge=0),
    offset: Optional[int] = Query(None, ge=0),
    lifecycle_status: Optional[str] = Query(None, alias="lifecycleStatus"),
):
    return _render_payload(
        _filter_and_page(categories, limit, offset, lifecycle_status), fields
    )


@app.post(f"{BASE_PATH}/category", status_code=201)
async def create_category(payload: CategoryFVO, fields: Optional[str] = Query(None)):
    payload_data = _model_payload(payload)
    category_id = payload_data.get("id") or f"category-{str(uuid.uuid4())[:8]}"
    created = Category(
        id=category_id,
        href=f"{BASE_PATH}/category/{category_id}",
        name=payload_data["name"],
        description=payload_data.get("description", ""),
        lifecycleStatus=payload_data.get("lifecycleStatus", "Active"),
        isRoot=payload_data.get("isRoot"),
        version=payload_data.get("version", "1.0"),
        validFor=payload_data.get("validFor") or _new_valid_for(),
        base_type=payload_data.get("@baseType"),
        schema_location=payload_data.get("@schemaLocation"),
        type_name=payload_data["@type"],
    )
    categories.append(created)
    return _render_payload(created, fields)


@app.get(f"{BASE_PATH}/category/{{category_id}}")
async def get_category(category_id: str, fields: Optional[str] = Query(None)):
    return _render_payload(_get_or_404(categories, category_id, "Category"), fields)


@app.patch(f"{BASE_PATH}/category/{{category_id}}")
async def patch_category(
    category_id: str, payload: CategoryMVO, fields: Optional[str] = Query(None)
):
    category = _get_or_404(categories, category_id, "Category")
    updated = _patch_model(category, _model_payload(payload))
    categories[categories.index(category)] = updated
    return _render_payload(updated, fields)


@app.delete(f"{BASE_PATH}/category/{{category_id}}", status_code=204)
async def delete_category(category_id: str):
    category = _get_or_404(categories, category_id, "Category")
    categories.remove(category)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get(f"{BASE_PATH}/productOffering")
async def get_product_offerings(
    fields: Optional[str] = Query(None),
    catalog_id: Optional[str] = Query(None),
    catalog_dot_id: Optional[str] = Query(None, alias="catalog.id"),
    limit: Optional[int] = Query(None, ge=0),
    offset: Optional[int] = Query(None, ge=0),
    lifecycle_status: Optional[str] = Query(None, alias="lifecycleStatus"),
):
    catalog_filter = catalog_id or catalog_dot_id
    filtered = product_offerings
    if catalog_filter:
        filtered = [po for po in filtered if po.catalogId == catalog_filter]
    return _render_payload(
        _filter_and_page(filtered, limit, offset, lifecycle_status), fields
    )


@app.post(f"{BASE_PATH}/productOffering", status_code=201)
async def create_product_offering(
    offering: ProductOfferingFVO, fields: Optional[str] = Query(None)
):
    payload_data = _model_payload(offering)
    category_refs = payload_data.get("category", [])
    catalog_id = payload_data.get("catalogId")

    if not catalog_id and category_refs:
        catalog_id = catalogs[0].id
    if not catalog_id:
        raise HTTPException(status_code=400, detail="catalogId is required by this mock")

    _get_or_404(catalogs, catalog_id, "Catalog")

    spec_id = f"ps-{str(uuid.uuid4())[:8]}"
    specification = ProductSpecification(
        id=spec_id,
        href=f"{BASE_PATH}/productSpecification/{spec_id}",
        name=f"{payload_data['name']} Specification",
        description=f"Technical specification for {payload_data['name']}",
        version=payload_data.get("version", "1.0"),
        validFor=payload_data.get("validFor") or _new_valid_for(),
        lifecycleStatus=payload_data["lifecycleStatus"],
        productSpecCharacteristic=[],
        type_name="ProductSpecification",
    )
    product_specifications.append(specification)

    category_models = [
        Category(
            id=entry["id"],
            href=entry.get("href") or f"{BASE_PATH}/category/{entry['id']}",
            name=entry.get("name", entry["id"]),
            description="",
            lifecycleStatus="Active",
            type_name=entry.get("@type", "Category"),
        )
        for entry in category_refs
        if "id" in entry
    ]
    if not category_models:
        category = next((entry for entry in categories if "general" in entry.id), None)
    else:
        category = None
    if category is None and not category_models:
        category = Category(
            id="category-general",
            href=f"{BASE_PATH}/category/category-general",
            name="General",
            description="General purpose offerings",
            type_name="Category",
        )
        categories.append(category)
    if not category_models and category is not None:
        category_models = [category]

    offering_id = f"po-{str(uuid.uuid4())[:8]}"
    created = ProductOffering(
        id=offering_id,
        href=f"{BASE_PATH}/productOffering/{offering_id}",
        name=payload_data["name"],
        description=payload_data.get("description", ""),
        version=payload_data.get("version", "1.0"),
        validFor=payload_data.get("validFor") or _new_valid_for(),
        lifecycleStatus=payload_data["lifecycleStatus"],
        isBundle=payload_data.get("isBundle", False),
        isSellable=payload_data.get("isSellable", True),
        catalogId=catalog_id,
        category=category_models,
        productSpecification=ProductSpecificationRef(
            id=specification.id,
            href=specification.href,
            name=specification.name,
            referred_type="ProductSpecification",
            type_name="ProductSpecificationRef",
        ),
        base_type=payload_data.get("@baseType"),
        schema_location=payload_data.get("@schemaLocation"),
        type_name=payload_data["@type"],
    )
    product_offerings.append(created)
    return _render_payload(created, fields)


@app.get(f"{BASE_PATH}/productOffering/{{offering_id}}")
async def get_product_offering(offering_id: str, fields: Optional[str] = Query(None)):
    return _render_payload(
        _get_or_404(product_offerings, offering_id, "Product offering"), fields
    )


@app.patch(f"{BASE_PATH}/productOffering/{{offering_id}}")
async def patch_product_offering(
    offering_id: str, payload: ProductOfferingMVO, fields: Optional[str] = Query(None)
):
    offering = _get_or_404(product_offerings, offering_id, "Product offering")
    updated = _patch_model(offering, _model_payload(payload))
    product_offerings[product_offerings.index(offering)] = updated
    return _render_payload(updated, fields)


@app.delete(f"{BASE_PATH}/productOffering/{{offering_id}}", status_code=204)
async def delete_product_offering(offering_id: str):
    offering = _get_or_404(product_offerings, offering_id, "Product offering")
    product_offerings.remove(offering)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get(f"{BASE_PATH}/productOfferingPrice")
async def get_product_offering_prices(
    fields: Optional[str] = Query(None),
    limit: Optional[int] = Query(None, ge=0),
    offset: Optional[int] = Query(None, ge=0),
    lifecycle_status: Optional[str] = Query(None, alias="lifecycleStatus"),
):
    return _render_payload(
        _filter_and_page(product_offering_prices, limit, offset, lifecycle_status),
        fields,
    )


@app.post(f"{BASE_PATH}/productOfferingPrice", status_code=201)
async def create_product_offering_price(
    payload: ProductOfferingPriceFVO, fields: Optional[str] = Query(None)
):
    payload_data = _model_payload(payload)
    price_id = payload_data.get("id") or f"pop-{str(uuid.uuid4())[:8]}"
    created = ProductOfferingPrice(
        id=price_id,
        href=f"{BASE_PATH}/productOfferingPrice/{price_id}",
        name=payload_data["name"],
        description=payload_data.get("description", ""),
        version=payload_data.get("version", "1.0"),
        lifecycleStatus=payload_data["lifecycleStatus"],
        priceType=payload_data["priceType"],
        lastUpdate=payload_data["lastUpdate"],
        price=payload_data.get("price") or Money(unit="USD", value=0),
        validFor=payload_data.get("validFor"),
        unitOfMeasure=payload_data.get("unitOfMeasure"),
        recurringChargePeriodType=payload_data.get("recurringChargePeriodType"),
        recurringChargePeriodLength=payload_data.get("recurringChargePeriodLength"),
        isBundle=payload_data.get("isBundle"),
        base_type=payload_data.get("@baseType"),
        schema_location=payload_data.get("@schemaLocation"),
        type_name=payload_data["@type"],
    )
    product_offering_prices.append(created)
    return _render_payload(created, fields)


@app.get(f"{BASE_PATH}/productOfferingPrice/{{price_id}}")
async def get_product_offering_price(price_id: str, fields: Optional[str] = Query(None)):
    return _render_payload(
        _get_or_404(product_offering_prices, price_id, "Product offering price"),
        fields,
    )


@app.patch(f"{BASE_PATH}/productOfferingPrice/{{price_id}}")
async def patch_product_offering_price(
    price_id: str, payload: ProductOfferingPriceMVO, fields: Optional[str] = Query(None)
):
    price = _get_or_404(product_offering_prices, price_id, "Product offering price")
    updated = _patch_model(price, _model_payload(payload))
    product_offering_prices[product_offering_prices.index(price)] = updated
    return _render_payload(updated, fields)


@app.delete(f"{BASE_PATH}/productOfferingPrice/{{price_id}}", status_code=204)
async def delete_product_offering_price(price_id: str):
    price = _get_or_404(product_offering_prices, price_id, "Product offering price")
    product_offering_prices.remove(price)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get(f"{BASE_PATH}/productSpecification")
async def get_product_specifications(
    fields: Optional[str] = Query(None),
    limit: Optional[int] = Query(None, ge=0),
    offset: Optional[int] = Query(None, ge=0),
    lifecycle_status: Optional[str] = Query(None, alias="lifecycleStatus"),
):
    return _render_payload(
        _filter_and_page(product_specifications, limit, offset, lifecycle_status),
        fields,
    )


@app.post(f"{BASE_PATH}/productSpecification", status_code=201)
async def create_product_specification(
    specification: ProductSpecificationFVO, fields: Optional[str] = Query(None)
):
    payload_data = _model_payload(specification)
    spec_id = f"ps-{str(uuid.uuid4())[:8]}"
    created = ProductSpecification(
        id=spec_id,
        href=f"{BASE_PATH}/productSpecification/{spec_id}",
        name=payload_data["name"],
        description=payload_data.get("description", ""),
        version=payload_data.get("version", "1.0"),
        validFor=payload_data.get("validFor") or _new_valid_for(),
        lifecycleStatus=payload_data["lifecycleStatus"],
        productSpecCharacteristic=payload_data.get("productSpecCharacteristic", []),
        brand=payload_data.get("brand"),
        base_type=payload_data.get("@baseType"),
        schema_location=payload_data.get("@schemaLocation"),
        type_name=payload_data["@type"],
    )
    product_specifications.append(created)
    return _render_payload(created, fields)


@app.get(f"{BASE_PATH}/productSpecification/{{spec_id}}")
async def get_product_specification(spec_id: str, fields: Optional[str] = Query(None)):
    return _render_payload(
        _get_or_404(product_specifications, spec_id, "Product specification"), fields
    )


@app.patch(f"{BASE_PATH}/productSpecification/{{spec_id}}")
async def patch_product_specification(
    spec_id: str, payload: ProductSpecificationMVO, fields: Optional[str] = Query(None)
):
    specification = _get_or_404(
        product_specifications, spec_id, "Product specification"
    )
    updated = _patch_model(specification, _model_payload(payload))
    product_specifications[product_specifications.index(specification)] = updated
    return _render_payload(updated, fields)


@app.delete(f"{BASE_PATH}/productSpecification/{{spec_id}}", status_code=204)
async def delete_product_specification(spec_id: str):
    specification = _get_or_404(
        product_specifications, spec_id, "Product specification"
    )
    product_specifications.remove(specification)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get(f"{BASE_PATH}/importJob")
async def get_import_jobs(
    fields: Optional[str] = Query(None),
    limit: Optional[int] = Query(None, ge=0),
    offset: Optional[int] = Query(None, ge=0),
):
    return _render_payload(_filter_and_page(import_jobs, limit, offset), fields)


@app.post(f"{BASE_PATH}/importJob", status_code=201)
async def create_import_job(payload: dict[str, Any], fields: Optional[str] = Query(None)):
    job_id = payload.get("id") or f"import-{str(uuid.uuid4())[:8]}"
    created = ImportJob(
        id=job_id,
        href=f"{BASE_PATH}/importJob/{job_id}",
        contentType=payload.get("contentType", "application/json"),
        creationDate=datetime.now(),
        path=payload.get("path", BASE_PATH),
        status=payload.get("status", "Running"),
        url=payload.get("url", f"ftp://example.com/{job_id}.json"),
        errorLog=payload.get("errorLog"),
    )
    import_jobs.append(created)
    return _render_payload(created, fields)


@app.get(f"{BASE_PATH}/importJob/{{job_id}}")
async def get_import_job(job_id: str, fields: Optional[str] = Query(None)):
    return _render_payload(_get_or_404(import_jobs, job_id, "Import job"), fields)


@app.delete(f"{BASE_PATH}/importJob/{{job_id}}", status_code=204)
async def delete_import_job(job_id: str):
    job = _get_or_404(import_jobs, job_id, "Import job")
    import_jobs.remove(job)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get(f"{BASE_PATH}/exportJob")
async def get_export_jobs(
    fields: Optional[str] = Query(None),
    limit: Optional[int] = Query(None, ge=0),
    offset: Optional[int] = Query(None, ge=0),
):
    return _render_payload(_filter_and_page(export_jobs, limit, offset), fields)


@app.post(f"{BASE_PATH}/exportJob", status_code=201)
async def create_export_job(payload: dict[str, Any], fields: Optional[str] = Query(None)):
    job_id = payload.get("id") or f"export-{str(uuid.uuid4())[:8]}"
    created = ExportJob(
        id=job_id,
        href=f"{BASE_PATH}/exportJob/{job_id}",
        contentType=payload.get("contentType", "application/json"),
        creationDate=datetime.now(),
        path=payload.get("path", f"{BASE_PATH}/productOffering"),
        query=payload.get("query", ""),
        status=payload.get("status", "Running"),
        url=payload.get("url", f"ftp://example.com/{job_id}.json"),
        errorLog=payload.get("errorLog"),
    )
    export_jobs.append(created)
    return _render_payload(created, fields)


@app.get(f"{BASE_PATH}/exportJob/{{job_id}}")
async def get_export_job(job_id: str, fields: Optional[str] = Query(None)):
    return _render_payload(_get_or_404(export_jobs, job_id, "Export job"), fields)


@app.delete(f"{BASE_PATH}/exportJob/{{job_id}}", status_code=204)
async def delete_export_job(job_id: str):
    job = _get_or_404(export_jobs, job_id, "Export job")
    export_jobs.remove(job)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post(f"{BASE_PATH}/hub", status_code=201)
async def create_hub(payload: HubFVO):
    payload_data = _model_payload(payload)
    callback = payload_data["callback"]
    hub_id = payload_data.get("id") or f"hub-{str(uuid.uuid4())[:8]}"
    created = Hub(
        id=hub_id,
        href=f"{BASE_PATH}/hub/{hub_id}",
        callback=callback,
        query=payload_data.get("query"),
        base_type=payload_data.get("@baseType"),
        schema_location=payload_data.get("@schemaLocation"),
        type_name=payload_data.get("@type", "Hub"),
    )
    hubs.append(created)
    return _render_payload(created)


@app.delete(f"{BASE_PATH}/hub/{{hub_id}}", status_code=204)
async def delete_hub(hub_id: str):
    hub = _get_or_404(hubs, hub_id, "Hub")
    hubs.remove(hub)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get(f"{BASE_PATH}/schema")
async def get_schema():
    return {
        "swagger": "2.0",
        "info": {
            "description": "TMF620 Product Catalog Management API",
            "version": "5.0.0",
            "title": "TMF620 Product Catalog Management",
        },
        "basePath": BASE_PATH,
        "paths": {
            "/productCatalog": {"get": {"description": "List all product catalogs"}},
            "/category": {"get": {"description": "List all categories"}},
            "/productOffering": {"get": {"description": "List all product offerings"}},
            "/productOfferingPrice": {
                "get": {"description": "List all product offering prices"}
            },
            "/productSpecification": {
                "get": {"description": "List all product specifications"}
            },
            "/importJob": {"get": {"description": "List all import jobs"}},
            "/exportJob": {"get": {"description": "List all export jobs"}},
            "/hub": {"post": {"description": "Create an event subscription hub"}},
        },
    }


def main():
    """Main entry point for the mock TMF620 API server."""
    import uvicorn

    if mock_config["features"]["enable_mcp"]:
        mcp.mount()

    server_config = mock_config["server"]
    print(
        f"Starting {server_config['name']} on "
        f"{server_config['protocol']}://{server_config['host']}:{server_config['port']}"
    )
    if mock_config["features"]["enable_mcp"]:
        print(
            f"MCP server available at "
            f"{server_config['protocol']}://{server_config['host']}:{server_config['port']}/mcp"
        )
    if mock_config["features"]["enable_docs"]:
        print(
            f"API Documentation available at "
            f"{server_config['protocol']}://{server_config['host']}:{server_config['port']}/docs"
        )

    uvicorn.run(app, host=server_config["host"], port=server_config["port"])


if __name__ == "__main__":
    main()
