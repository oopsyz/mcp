"""Check the cacheable GET-help profile on a running HTTP CLI endpoint."""

import argparse
from uuid import uuid4

import requests


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def check_discovery(http, endpoint, command, previous_etag=None):
    """Return the current target ETag, suitable for a check after metadata changes."""
    root = http.get(endpoint, timeout=10)
    require(
        root.status_code == 200 and root.json().get("help_get") is True,
        "Root must advertise help_get",
    )
    params = {"command": command}
    headers = {"If-None-Match": previous_etag} if previous_etag else {}
    leaf = http.get(endpoint, params=params, headers=headers, timeout=10)
    require(leaf.status_code == 200, "Expected a fresh 200 help representation")
    tag = leaf.headers.get("etag")
    require(tag and tag != previous_etag, "Expected a current, distinct help ETag")
    require(
        leaf.json().get("command") == command and leaf.json().get("status") == "ok",
        "GET must return help for the specified target",
    )
    posted = http.post(endpoint, json={"command": "help", "args": params}, timeout=10)
    require(
        posted.status_code == 200 and posted.json() == leaf.json(),
        "GET/POST help differs",
    )

    for resource, target in [(root, {}), (leaf, params)]:
        validator = resource.headers.get("etag")
        policy = resource.headers.get("cache-control")
        require(validator and policy, "Expected explicit cache policy and ETag")
        weak = validator if validator.startswith("W/") else "W/" + validator
        same = http.get(
            endpoint,
            params=target,
            headers={"If-None-Match": f'"other", {weak}'},
            timeout=10,
        )
        require(same.status_code == 304 and not same.content, "Expected bodyless 304")
        require(
            same.headers.get("etag") == validator
            and same.headers.get("cache-control") == policy,
            "304 must retain cache metadata",
        )

    unknown = {"command": f"missing-{uuid4().hex}"}
    errors = [
        http.get(endpoint, params=unknown, timeout=10),
        http.post(endpoint, json={"command": "help", "args": unknown}, timeout=10),
    ]
    for error in errors:
        require(
            error.status_code == 404
            and error.json()["error"]["code"] == "help_target_not_found",
            "Expected a 404 help_target_not_found error",
        )
    return tag


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("endpoint")
    parser.add_argument("command")
    parser.add_argument(
        "--previous-etag",
        help="Target ETag captured before changing this command's help",
    )
    options = parser.parse_args()
    with requests.Session() as session:
        print(
            check_discovery(
                session, options.endpoint, options.command, options.previous_etag
            )
        )
