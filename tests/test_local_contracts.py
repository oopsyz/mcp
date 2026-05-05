import pytest
from fastapi.testclient import TestClient

from tmf620.commands import CommandInvocationError, get_command_help_payload, invoke_command
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
