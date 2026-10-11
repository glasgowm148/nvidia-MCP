import httpx
import pytest

from nvidia_mcp.config import Config, ShieldError
from nvidia_mcp.transport import Transport


def test_http_auth_and_no_redirects():
    transport = Transport(Config(host="127.0.0.1", username="kodi", password="private"))
    requests = []

    def handler(req):
        requests.append(req)
        return httpx.Response(302, headers={"Location": "https://example.com"})

    transport.http.close()
    transport.http = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    with pytest.raises(ShieldError, match="302"):
        transport.rpc("JSONRPC.Version")
    assert len(requests) == 1 and requests[0].headers["authorization"].startswith("Basic ")
    transport.close()


def test_http_limit_and_errors_do_not_echo_server_body():
    transport = Transport(Config(host="127.0.0.1"))
    transport.http.close()
    transport.http = httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, content=b"x" * 4_000_001))
    )
    with pytest.raises(ShieldError, match="4 MB"):
        transport.rpc("JSONRPC.Version")
    transport.close()
    transport.http = httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(401, text="secret-token"))
    )
    with pytest.raises(ShieldError) as exc:
        transport.rpc("JSONRPC.Version")
    assert "secret-token" not in str(exc.value)
    transport.close()


def manager_transport(status, body):
    transport = Transport(Config(host="127.0.0.1", manager_token="synthetic-manager-token"))
    transport.http.close()
    transport.http = httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(status, json=body))
    )
    return transport


def envelope(code, message):
    return {"ok": False, "code": code, "error": {"code": code, "message": message, "details": {}}}


@pytest.mark.parametrize(
    "status,code,message,kind,shown",
    [
        (403, "write_disabled", "Write Mode is disabled", "write_disabled", "Write Mode"),
        (403, "origin_mismatch", "Cross-origin request rejected", "origin_mismatch", "origin"),
        (409, "playback_active", "Stop playback before restoring", "playback_active", "playback"),
        (400, "playback_active", "Playback is active", "playback_active", "playback"),
        (400, "invalid_value", "Expected a whole number", "invalid_request", "whole number"),
        (500, "server_error", "Widget cache is busy", "service_error", "Widget cache is busy"),
        (404, "not_found", "Add-on not installed", "not_found", "not installed"),
    ],
)
def test_manager_errors_keep_their_code_and_message(status, code, message, kind, shown):
    transport = manager_transport(status, envelope(code, message))
    with pytest.raises(ShieldError) as exc:
        transport.manager("/api/widget-cache")
    assert exc.value.kind == kind and shown in str(exc.value)
    # Only a missing route may suggest a newer companion; credentials are not the problem.
    assert "newer Kodi Manager" not in str(exc.value)
    assert "Authentication" not in str(exc.value)


def test_manager_auth_and_missing_routes_are_distinct():
    with pytest.raises(ShieldError) as exc:
        manager_transport(401, envelope("unauthorized", "Missing or invalid bearer token")).manager(
            "/api/health"
        )
    assert exc.value.kind == "authentication_denied"
    with pytest.raises(ShieldError) as exc:
        manager_transport(404, envelope("not_found", "Route not found")).manager(
            "/api/widget-cache"
        )
    assert exc.value.kind == "unsupported"


def test_manager_error_messages_are_redacted():
    message = "Bad value synthetic-manager-token for rd.auth=FAKE-TOKEN-1"
    with pytest.raises(ShieldError) as exc:
        manager_transport(400, envelope("invalid_value", message)).manager("/api/addons/x/settings")
    assert "synthetic-manager-token" not in str(exc.value)
    assert "FAKE-TOKEN-1" not in str(exc.value)


def test_widget_cache_only_reports_old_manager_for_missing_routes(ops):
    from dataclasses import replace

    ops.c = replace(ops.c, manager_token="synthetic-manager-token")
    for status, body, expected in [
        (500, envelope("server_error", "Widget cache is busy"), "busy"),
        (404, envelope("not_found", "Route not found"), "0.6"),
    ]:
        transport = manager_transport(status, body)
        ops.t.manager = transport.manager
        with pytest.raises(ShieldError, match=expected):
            ops.widget_cache()
