from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

import requests


DEFAULT_API_URL = "http://localhost:8801/tmf-api/productCatalogManagement/v4"
DEFAULT_MCP_HOST = "localhost"
DEFAULT_MCP_PORT = 7701
DEFAULT_MCP_NAME = "TMF620 Product Catalog API"

DEFAULT_ENDPOINTS = {
    "catalog_list": "/catalog",
    "catalog_detail": "/catalog/{id}",
    "product_offering_list": "/productOffering",
    "product_offering_detail": "/productOffering/{id}",
    "product_specification_list": "/productSpecification",
    "product_specification_detail": "/productSpecification/{id}",
    "product_offering_create": "/productOffering",
    "schema": "/schema",
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
    tmf620_api["url"] = tmf620_api.get("url") or os.environ.get(
        "TMF620_API_URL", DEFAULT_API_URL
    )

    mcp_server = config.setdefault("mcp_server", {})
    mcp_server["host"] = mcp_server.get("host") or os.environ.get(
        "MCP_HOST", DEFAULT_MCP_HOST
    )
    mcp_server["port"] = mcp_server.get("port") or int(
        os.environ.get("MCP_PORT", str(DEFAULT_MCP_PORT))
    )
    mcp_server["name"] = mcp_server.get("name") or os.environ.get(
        "MCP_NAME", DEFAULT_MCP_NAME
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

    def test_connection(self) -> None:
        """Validate that the backing TMF620 API is reachable."""
        try:
            self.request("GET", self.endpoints["catalog_list"], timeout=10)
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

        valid_methods = {"GET", "POST", "PUT", "DELETE"}
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
                params=params,
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
            self.request("GET", self.endpoints["catalog_list"])
            payload["api_connection"] = "successful"
        except TMF620Error as exc:
            payload["api_connection"] = "failed"
            payload["error"] = str(exc)
        return payload

    def list_catalogs(self) -> Any:
        return self.request("GET", self.endpoints["catalog_list"])

    def get_catalog(self, catalog_id: str) -> Any:
        endpoint = self.endpoints["catalog_detail"].format(id=catalog_id)
        return self.request("GET", endpoint)

    def list_product_offerings(self, catalog_id: Optional[str] = None) -> Any:
        params: Dict[str, Any] = {}
        if catalog_id and catalog_id.lower() not in {"null", ""}:
            params["catalog.id"] = catalog_id
        return self.request(
            "GET", self.endpoints["product_offering_list"], params=params or None
        )

    def get_product_offering(self, offering_id: str) -> Any:
        endpoint = self.endpoints["product_offering_detail"].format(id=offering_id)
        return self.request("GET", endpoint)

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
        return self.request(
            "POST", self.endpoints["product_offering_create"], json_data=payload
        )

    def list_product_specifications(self) -> Any:
        return self.request("GET", self.endpoints["product_specification_list"])

    def get_product_specification(self, specification_id: str) -> Any:
        endpoint = self.endpoints["product_specification_detail"].format(
            id=specification_id
        )
        return self.request("GET", endpoint)

    def create_product_specification(
        self, name: str, description: str, version: str = "1.0"
    ) -> Any:
        payload = {
            "name": name,
            "description": description,
            "version": version,
            "lifecycleStatus": "Active",
        }
        return self.request(
            "POST", self.endpoints["product_specification_list"], json_data=payload
        )
