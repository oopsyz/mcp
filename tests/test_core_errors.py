import pytest
import requests

from tmf620.core import (
    DEFAULT_ENDPOINTS,
    TMF620Client,
    TMF620ConnectionError,
    TMF620HTTPClientError,
    TMF620HTTPServerError,
    TMF620ResponseError,
    TMF620TimeoutError,
    load_config,
)


class DummyResponse:
    def __init__(self, status_code=200, payload=None, text="", content=b"x"):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)

    def json(self):
        if isinstance(self._payload, BaseException):
            raise self._payload
        return self._payload


def test_http_4xx_raises_client_error(monkeypatch):
    def fake_request(*args, **kwargs):
        return DummyResponse(status_code=404, payload={"error": "not found"})

    monkeypatch.setattr(requests, "request", fake_request)
    client = TMF620Client(config={"tmf620_api": {"url": "http://example"}, "endpoints": {}})

    with pytest.raises(TMF620HTTPClientError) as exc_info:
        client.request("GET", "/missing")

    assert exc_info.value.status_code == 404
    assert exc_info.value.retryable is False
    assert exc_info.value.detail == {"error": "not found"}


def test_http_5xx_raises_server_error(monkeypatch):
    def fake_request(*args, **kwargs):
        return DummyResponse(status_code=503, text="unavailable", content=b"unavailable")

    monkeypatch.setattr(requests, "request", fake_request)
    client = TMF620Client(config={"tmf620_api": {"url": "http://example"}, "endpoints": {}})

    with pytest.raises(TMF620HTTPServerError) as exc_info:
        client.request("GET", "/down")

    assert exc_info.value.status_code == 503
    assert exc_info.value.retryable is True
    assert exc_info.value.detail == "unavailable"


def test_timeout_and_connection_errors_are_typed(monkeypatch):
    client = TMF620Client(config={"tmf620_api": {"url": "http://example"}, "endpoints": {}})

    def timeout_request(*args, **kwargs):
        raise requests.exceptions.Timeout()

    monkeypatch.setattr(requests, "request", timeout_request)
    with pytest.raises(TMF620TimeoutError):
        client.request("GET", "/slow")

    def connection_request(*args, **kwargs):
        raise requests.exceptions.ConnectionError()

    monkeypatch.setattr(requests, "request", connection_request)
    with pytest.raises(TMF620ConnectionError):
        client.request("GET", "/offline")


def test_invalid_json_response_is_typed(monkeypatch):
    def fake_request(*args, **kwargs):
        return DummyResponse(payload=requests.exceptions.JSONDecodeError("bad", "", 0))

    monkeypatch.setattr(requests, "request", fake_request)
    client = TMF620Client(config={"tmf620_api": {"url": "http://example"}, "endpoints": {}})

    with pytest.raises(TMF620ResponseError):
        client.request("GET", "/bad-json")


def test_packaged_config_endpoint_defaults_are_consistent():
    config = load_config()

    for key, endpoint in DEFAULT_ENDPOINTS.items():
        assert config["endpoints"][key] == endpoint
