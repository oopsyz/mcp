from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

import requests


DEFAULT_API_URL = "http://localhost:8801/tmf-api/productCatalogManagement/v5"
DEFAULT_MCP_HOST = "localhost"
DEFAULT_MCP_PORT = 7701
DEFAULT_MCP_NAME = "TMF620 Product Catalog API"

DEFAULT_ENDPOINTS = {
    "category_list": "/category",
    "category_detail": "/category/{id}",
    "export_job_list": "/exportJob",
    "export_job_detail": "/exportJob/{id}",
    "hub_create": "/hub",
    "hub_delete": "/hub/{id}",
    "import_job_list": "/importJob",
    "import_job_detail": "/importJob/{id}",
    "product_catalog_list": "/productCatalog",
    "product_catalog_detail": "/productCatalog/{id}",
    "product_offering_list": "/productOffering",
    "product_offering_detail": "/productOffering/{id}",
    "product_offering_price_list": "/productOfferingPrice",
    "product_offering_price_detail": "/productOfferingPrice/{id}",
    "product_specification_list": "/productSpecification",
    "product_specification_detail": "/productSpecification/{id}",
    "schema": "/schema",
}

RESOURCE_ENDPOINT_ALIASES = {
    "category": ("category_list", "category_detail"),
    "export_job": ("export_job_list", "export_job_detail"),
    "import_job": ("import_job_list", "import_job_detail"),
    "product_catalog": ("product_catalog_list", "product_catalog_detail"),
    "catalog": ("product_catalog_list", "product_catalog_detail"),
    "product_offering": ("product_offering_list", "product_offering_detail"),
    "product_offering_price": (
        "product_offering_price_list",
        "product_offering_price_detail",
    ),
    "product_specification": (
        "product_specification_list",
        "product_specification_detail",
    ),
}

logger = logging.getLogger("tmf620")


class TMF620Error(Exception):
    """Raised when the TMF620 API returns an error or cannot be reached."""


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from file, then fill gaps from environment variables."""
    config: Dict[str, Any] = {}
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_config_path = os.path.join(script_dir, "config.json")
    resolved_config_path = (
        config_path or os.environ.get("TMF620_CONFIG_PATH") or default_config_path
    )

    try:
        logger.info("Attempting to load config from %s", resolved_config_path)
        with open(resolved_config_path, encoding="utf-8") as config_file:
            config = json.load(config_file)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning("Could not load config from %s: %s", resolved_config_path, exc)
        logger.info("Falling back to environment variables")

    tmf620_api = config.setdefault("tmf620_api", {})
    tmf620_api["url"] = os.environ.get(
        "TMF620_API_URL",
        tmf620_api.get("url") or DEFAULT_API_URL,
    )

    mcp_server = config.setdefault("mcp_server", {})
    mcp_server["host"] = os.environ.get(
        "MCP_HOST",
        mcp_server.get("host") or DEFAULT_MCP_HOST,
    )
    mcp_server["port"] = int(
        os.environ.get(
            "MCP_PORT",
            str(mcp_server.get("port") or DEFAULT_MCP_PORT),
        )
    )
    mcp_server["name"] = os.environ.get(
        "MCP_NAME",
        mcp_server.get("name") or DEFAULT_MCP_NAME,
    )

    config["endpoints"] = {**DEFAULT_ENDPOINTS, **config.get("endpoints", {})}

    logger.info("TMF620 API URL: %s", tmf620_api["url"])
    logger.info("MCP Server: %s:%s", mcp_server["host"], mcp_server["port"])
    return config


class TMF620Client:
    """Thin client around the TMF620 Product Catalog Management API."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        config_path: Optional[str] = None,
        timeout: int = 30,
    ) -> None:
        self.config = config or load_config(config_path=config_path)
        self.timeout = timeout

    @property
    def api_url(self) -> str:
        return self.config["tmf620_api"]["url"]

    @property
    def endpoints(self) -> Dict[str, str]:
        return self.config["endpoints"]

    def _resolve_endpoint(self, *keys: str) -> str:
        for key in keys:
            endpoint = self.endpoints.get(key)
            if endpoint:
                return endpoint
        raise TMF620Error(f"No endpoint configured for keys: {', '.join(keys)}")

    def _resource_endpoint_keys(self, resource_name: str) -> tuple[str, str]:
        aliases = RESOURCE_ENDPOINT_ALIASES.get(resource_name)
        if aliases is None:
            raise TMF620Error(f"Unsupported TMF620 resource: {resource_name}")
        return aliases

    def _resource_paths(self, resource_name: str) -> tuple[str, str]:
        list_key, detail_key = self._resource_endpoint_keys(resource_name)
        return (self._resolve_endpoint(list_key), self._resolve_endpoint(detail_key))

    @staticmethod
    def _clean_params(params: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not params:
            return None
        cleaned = {
            key: value
            for key, value in params.items()
            if value is not None and value != ""
        }
        return cleaned or None

    def test_connection(self) -> None:
        """Validate that the backing TMF620 API is reachable."""
        try:
            self.request("GET", self._resolve_endpoint("product_catalog_list"), timeout=10)
        except TMF620Error:
            raise

    def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        """Execute an HTTP request against the configured TMF620 API."""
        if not endpoint.startswith("/"):
            raise ValueError("Endpoint must start with '/'")

        valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE"}
        normalized_method = method.upper()
        if normalized_method not in valid_methods:
            raise ValueError(
                f"Invalid method {method}. Must be one of {sorted(valid_methods)}"
            )

        url = f"{self.api_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "TMF620-Client/1.0",
        }

        logger.info("Making %s request to %s", normalized_method, url)
        try:
            response = requests.request(
                normalized_method,
                url,
                params=self._clean_params(params),
                json=json_data,
                headers=headers,
                timeout=timeout or self.timeout,
            )
            response.raise_for_status()

            if not response.content:
                return {}

            return response.json()
        except requests.exceptions.HTTPError as exc:
            error_detail: Any = "Unknown error"
            if exc.response is not None:
                try:
                    if exc.response.content:
                        error_detail = exc.response.json()
                except ValueError:
                    error_detail = (
                        exc.response.text
                        if exc.response.text
                        else f"HTTP {exc.response.status_code}"
                    )
                raise TMF620Error(
                    f"TMF620 API error: {exc.response.status_code} - {error_detail}"
                ) from exc
            raise TMF620Error(f"TMF620 API HTTP error: {exc}") from exc
        except requests.exceptions.ConnectionError as exc:
            raise TMF620Error(
                f"Could not connect to TMF620 API at {self.api_url}. "
                "Is the server running on the configured URL?"
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise TMF620Error(
                f"TMF620 API request timed out after {timeout or self.timeout} seconds"
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise TMF620Error(f"Error making request to TMF620 API: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise TMF620Error("Invalid JSON response from TMF620 API") from exc

    def health(self) -> Dict[str, Any]:
        """Return a health payload that reflects API reachability."""
        payload = {
            "status": "healthy",
            "api_url": self.api_url,
        }
        try:
            self.request("GET", self._resolve_endpoint("product_catalog_list"))
            payload["api_connection"] = "successful"
        except TMF620Error as exc:
            payload["api_connection"] = "failed"
            payload["error"] = str(exc)
        return payload

    def list_resource(
        self,
        resource_name: str,
        *,
        fields: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Any:
        list_endpoint, _ = self._resource_paths(resource_name)
        params: Dict[str, Any] = {"fields": fields, "limit": limit, "offset": offset}
        if filters:
            params.update(filters)
        return self.request("GET", list_endpoint, params=params)

    def get_resource(
        self,
        resource_name: str,
        resource_id: str,
        *,
        fields: Optional[str] = None,
    ) -> Any:
        _, detail_endpoint = self._resource_paths(resource_name)
        endpoint = detail_endpoint.format(id=resource_id)
        return self.request("GET", endpoint, params={"fields": fields})

    def create_resource(
        self,
        resource_name: str,
        payload: Dict[str, Any],
        *,
        fields: Optional[str] = None,
    ) -> Any:
        list_endpoint, _ = self._resource_paths(resource_name)
        return self.request(
            "POST",
            list_endpoint,
            params={"fields": fields},
            json_data=payload,
        )

    def patch_resource(
        self,
        resource_name: str,
        resource_id: str,
        payload: Dict[str, Any],
        *,
        fields: Optional[str] = None,
    ) -> Any:
        _, detail_endpoint = self._resource_paths(resource_name)
        endpoint = detail_endpoint.format(id=resource_id)
        return self.request(
            "PATCH",
            endpoint,
            params={"fields": fields},
            json_data=payload,
        )

    def delete_resource(self, resource_name: str, resource_id: str) -> Any:
        _, detail_endpoint = self._resource_paths(resource_name)
        endpoint = detail_endpoint.format(id=resource_id)
        return self.request("DELETE", endpoint)

    def create_hub(self, payload: Dict[str, Any]) -> Any:
        endpoint = self._resolve_endpoint("hub_create")
        return self.request("POST", endpoint, json_data=payload)

    def delete_hub(self, hub_id: str) -> Any:
        endpoint = self._resolve_endpoint("hub_delete").format(id=hub_id)
        return self.request("DELETE", endpoint)

    def list_catalogs(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        lifecycle_status: Optional[str] = None,
    ) -> Any:
        return self.list_resource(
            "catalog",
            limit=limit,
            offset=offset,
            filters={"lifecycleStatus": lifecycle_status},
        )

    def get_catalog(self, catalog_id: str) -> Any:
        return self.get_resource("catalog", catalog_id)

    def list_product_offerings(
        self,
        catalog_id: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        lifecycle_status: Optional[str] = None,
    ) -> Any:
        filters: Dict[str, Any] = {"lifecycleStatus": lifecycle_status}
        if catalog_id and catalog_id.lower() not in {"null", ""}:
            filters["catalog.id"] = catalog_id
        return self.list_resource(
            "product_offering",
            limit=limit,
            offset=offset,
            filters=filters,
        )

    def get_product_offering(self, offering_id: str) -> Any:
        return self.get_resource("product_offering", offering_id)

    def create_product_offering(
        self, name: str, description: str, catalog_id: str
    ) -> Any:
        payload = {
            "name": name,
            "description": description,
            "catalogId": catalog_id,
            "lifecycleStatus": "Active",
            "version": "1.0",
        }
        return self.create_resource("product_offering", payload)

    def delete_product_offering(self, offering_id: str) -> Any:
        return self.delete_resource("product_offering", offering_id)

    def list_product_specifications(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        lifecycle_status: Optional[str] = None,
    ) -> Any:
        return self.list_resource(
            "product_specification",
            limit=limit,
            offset=offset,
            filters={"lifecycleStatus": lifecycle_status},
        )

    def get_product_specification(self, specification_id: str) -> Any:
        return self.get_resource("product_specification", specification_id)

    def create_product_specification(
        self, name: str, description: str, version: str = "1.0"
    ) -> Any:
        payload = {
            "name": name,
            "description": description,
            "version": version,
            "lifecycleStatus": "Active",
        }
        return self.create_resource("product_specification", payload)
