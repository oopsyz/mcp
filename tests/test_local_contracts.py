import pytest
from fastapi.testclient import TestClient

from tmf620 import commands
from tmf620.commands import (
    RESOURCE_PATH_ALIASES,
    RESOURCE_SPECS,
    CommandInvocationError,
    get_command_help_payload,
    invoke_command,
)
from tmf620.mock_api import BASE_PATH, app as mock_app


def test_help_command_is_self_describing():
    payload = get_command_help_payload("help")

    assert payload is not None
    assert payload["status"] == "ok"
    assert payload["command"] == "help"
    assert payload["arguments"][0]["name"] == "command"


def test_non_payload_commands_reject_payload_aliases():
    with pytest.raises(CommandInvocationError) as exc_info:
        invoke_command("config", {"body": {"unexpected": True}})

    assert exc_info.value.code == "invalid_argument"
    assert "body" in str(exc_info.value)


def test_mock_product_offering_create_accepts_client_payload():
    client = TestClient(mock_app)

    response = client.post(
        f"{BASE_PATH}/productOffering",
        json={
            "name": "Compatibility Offering",
            "description": "Created through the packaged client payload shape",
            "catalogId": "cat-001",
            "lifecycleStatus": "Active",
            "version": "1.0",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Compatibility Offering"
    assert body["catalogId"] == "cat-001"
    assert body["@type"] == "ProductOffering"


def test_resource_path_help_is_discoverable():
    group = get_command_help_payload("/catalogs")
    assert group is not None
    assert group["kind"] == "group"
    assert any(command["name"] == "/catalogs list" for command in group["subcommands"])

    leaf = get_command_help_payload("/catalogs list")
    assert leaf is not None
    assert leaf["status"] == "ok"
    assert leaf["command"] == "/catalogs list"
    assert leaf["summary"] == "Resource path alias for catalog list."


def test_resource_path_invocation_translates_to_curated_command(monkeypatch):
    calls = []

    class FakeClient:
        def __init__(self, config_path=None):
            self.config_path = config_path

        def list_resource(self, resource_name, *, fields=None, limit=None, offset=None, filters=None):
            calls.append(
                {
                    "method": "list_resource",
                    "resource_name": resource_name,
                    "fields": fields,
                    "limit": limit,
                    "offset": offset,
                    "filters": filters,
                }
            )
            return [{"id": "cat-001", "name": "Enterprise Services Catalog"}]

        def get_resource(self, resource_name, resource_id, *, fields=None):
            calls.append(
                {
                    "method": "get_resource",
                    "resource_name": resource_name,
                    "resource_id": resource_id,
                    "fields": fields,
                }
            )
            return {"id": resource_id, "name": "Enterprise Services Catalog"}

    monkeypatch.setattr(commands, "TMF620Client", FakeClient)

    listed = invoke_command(
        "/catalogs list",
        {"fields": "id,name", "limit": 1, "lifecycle_status": "Active"},
    )
    assert listed == [{"id": "cat-001", "name": "Enterprise Services Catalog"}]
    assert calls[-1] == {
        "method": "list_resource",
        "resource_name": "product_catalog",
        "fields": "id,name",
        "limit": 1,
        "offset": None,
        "filters": {"lifecycleStatus": "Active"},
    }

    got = invoke_command("/catalogs/cat-001 get", {"fields": "id,name"})
    assert got["id"] == "cat-001"
    assert calls[-1] == {
        "method": "get_resource",
        "resource_name": "product_catalog",
        "resource_id": "cat-001",
        "fields": "id,name",
    }


def test_resource_path_mode_rejects_raw_proxy_shapes():
    with pytest.raises(CommandInvocationError) as exc_info:
        invoke_command("/tmf-api/productCatalogManagement/v5/productCatalog GET")

    assert exc_info.value.code == "command_not_found"

    with pytest.raises(CommandInvocationError) as missing_id:
        invoke_command("/catalogs get")

    assert missing_id.value.code == "missing_required_argument"


def test_resource_path_aliases_are_generated_from_resource_specs():
    expected_alias_count = sum(
        len(resource_spec.get("path_aliases", ())) for resource_spec in RESOURCE_SPECS
    )

    assert len(RESOURCE_PATH_ALIASES) == expected_alias_count
    for resource_spec in RESOURCE_SPECS:
        for alias in resource_spec.get("path_aliases", ()):
            assert RESOURCE_PATH_ALIASES[alias] == resource_spec["command"]


def test_resource_path_rejects_nested_paths_with_encoding_hint():
    with pytest.raises(CommandInvocationError) as exc_info:
        invoke_command("/catalogs/cat-001/admin get")

    assert exc_info.value.code == "command_not_found"
    assert "Resource-path mode supports" in str(exc_info.value)


def test_resource_path_rejects_encoded_slash_in_id():
    with pytest.raises(CommandInvocationError) as exc_info:
        invoke_command("/catalogs/cat-001%2Fadmin get")

    assert exc_info.value.code == "invalid_command"
    assert "explicit ID argument" in str(exc_info.value)
