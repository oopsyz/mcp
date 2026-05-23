import asyncio
import inspect
import json

import httpx

from tmf620 import server
from tmf620.commands import COMMAND_TREE


def _command_node(*path):
    nodes = COMMAND_TREE
    node = None
    for segment in path:
        node = next(candidate for candidate in nodes if candidate["name"] == segment)
        nodes = node.get("commands", [])
    return node


def test_streaming_chunks_for_list_result():
    chunks = list(
        server._streaming_result_chunks(
            "catalog list",
            {},
            [{"id": "cat-001"}, {"id": "cat-002"}],
        )
    )

    parsed = [json.loads(chunk) for chunk in chunks]
    assert parsed[0]["type"] == "started"
    assert [chunk["type"] for chunk in parsed[1:]] == ["item", "item", "done"]
    assert parsed[-1]["total"] == 2


def test_streaming_chunks_for_items_envelope_preserve_metadata():
    chunks = list(
        server._streaming_result_chunks(
            "catalog list",
            {},
            {"items": [{"id": "cat-001"}], "next": "cursor-1"},
        )
    )

    parsed = [json.loads(chunk) for chunk in chunks]
    assert [chunk["type"] for chunk in parsed] == ["started", "item", "done"]
    assert parsed[-1]["total"] == 1
    assert parsed[-1]["next"] == "cursor-1"


def test_mcp_tool_parameters_convert_payload_args_to_body():
    node = _command_node("catalog", "create")

    parameters = server._mcp_tool_parameters(node)

    assert parameters[0]["name"] == "body"
    assert parameters[0]["required"] is True
    assert "body_json" not in {parameter["name"] for parameter in parameters}
    assert "body_file" not in {parameter["name"] for parameter in parameters}


def test_mcp_tool_parameters_include_append_as_list():
    node = _command_node("catalog", "list")

    parameters = server._mcp_tool_parameters(node)
    filters = next(parameter for parameter in parameters if parameter["name"] == "filters")

    assert filters["required"] is False
    assert filters["annotation"] == "list[str] | None"


def test_mcp_tool_callable_signature_and_invocation(monkeypatch):
    calls = []

    def fake_invoke(command, args, *, config_path=None, output="json"):
        calls.append(
            {
                "command": command,
                "args": args,
                "config_path": config_path,
                "output": output,
            }
        )
        return {"ok": True}

    monkeypatch.setattr(server, "invoke_command", fake_invoke)
    tool = server._build_mcp_tool_callable(
        function_name="tmf620_catalog_create",
        command="catalog create",
        summary="Create catalog",
        description="Create catalog.",
        parameters=[
            {
                "name": "body",
                "python_type": dict[str, object],
                "required": True,
                "description": "JSON body.",
            },
            {
                "name": "fields",
                "python_type": str | None,
                "required": False,
                "description": "Fields.",
            },
        ],
    )

    signature = inspect.signature(tool)
    assert list(signature.parameters) == ["body", "fields"]

    result = asyncio.run(tool(body={"name": "Demo"}, fields="id,name"))

    assert result == {"ok": True}
    assert calls == [
        {
            "command": "catalog create",
            "args": {"body": {"name": "Demo"}, "fields": "id,name"},
            "config_path": None,
            "output": "json",
        }
    ]


def test_cli_dispatch_handles_concurrent_requests(monkeypatch):
    calls = []

    def fake_invoke(command, args, *, config_path=None, output="json"):
        calls.append(command)
        return {"command": command, "args": args}

    monkeypatch.setattr(server, "invoke_command", fake_invoke)

    async def run_requests():
        transport = httpx.ASGITransport(app=server.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            responses = await asyncio.gather(
                *[
                    client.post(
                        server.CLI_ROUTE,
                        json={"command": "health", "args": {"seq": index}},
                    )
                    for index in range(10)
                ]
            )
        return responses

    responses = asyncio.run(run_requests())

    assert len(responses) == 10
    for response in responses:
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["command"] == "health"
    assert calls == ["health"] * 10
