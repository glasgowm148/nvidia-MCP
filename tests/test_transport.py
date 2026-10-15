import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from nvidia_mcp.config import Config, ShieldError
from nvidia_mcp.transport import Transport


@pytest.mark.parametrize("enabled_only", [False, True])
def test_addons_listing_with_kodi_field_validation(tmp_path, enabled_only):
    from nvidia_mcp.operations import Operations

    transport = Transport(Config(host="127.0.0.1", state=tmp_path))

    def kodi(request):
        body = json.loads(request.content)
        assert body["method"] == "Addons.GetAddons"
        params = body["params"]
        # Addon.Fields excludes type; Kodi always includes it in Addon.Details.
        allowed = {
            "name",
            "version",
            "summary",
            "description",
            "path",
            "author",
            "thumbnail",
            "disclaimer",
            "fanart",
            "dependencies",
            "broken",
            "extrainfo",
            "rating",
            "enabled",
            "installed",
        }
        if not set(params.get("properties", [])).issubset(allowed):
            return httpx.Response(
                200, json={"error": {"code": -32602, "message": "Invalid params."}}
            )
        assert params.get("enabled") is (True if enabled_only else None)
        return httpx.Response(
            200,
            json={
                "result": {
                    "addons": [
                        {
                            "addonid": "plugin.video.example",
                            "name": "Example",
                            "version": "1.0.0",
                            "type": "xbmc.python.pluginsource",
                            "enabled": True,
                        }
                    ]
                }
            },
        )

    transport.http.close()
    transport.http = httpx.Client(transport=httpx.MockTransport(kodi))
    try:
        result = Operations(transport).addons(enabled_only)
        assert result["addons"][0]["type"] == "xbmc.python.pluginsource"
    finally:
        transport.close()


def forwarded_transport(tmp_path, route="forward"):
    transport = Transport(
        Config(host="192.168.0.20", state=tmp_path, manager_token="synthetic", http_route=route)
    )
    calls = []

    def adb(*args, **kwargs):
        calls.append(args)
        return b"41235" if args[-1] == "tcp:8765" else b"41234"

    transport.adb = adb
    transport.http.close()
    return transport, calls


def test_forward_route_reaches_both_services_once_and_cleans_up(tmp_path):
    transport, calls = forwarded_transport(tmp_path)

    def handler(request):
        assert request.url.host == "127.0.0.1"
        if request.url.port == 41235:
            assert request.headers["Authorization"] == "Bearer synthetic"
            return httpx.Response(200, json={"ok": True, "data": {"service": "manager"}})
        assert request.url.port == 41234
        return httpx.Response(200, json={"result": "pong"})

    transport.http = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(
                pool.map(
                    lambda _: (transport.rpc("JSONRPC.Ping"), transport.manager("/api/health")),
                    range(8),
                )
            )
        assert all(result == ("pong", {"service": "manager"}) for result in results)
        assert calls == [("forward", "tcp:0", "tcp:8080"), ("forward", "tcp:0", "tcp:8765")]
    finally:
        transport.close()
    assert calls[-2:] == [
        ("forward", "--remove", "tcp:41234"),
        ("forward", "--remove", "tcp:41235"),
    ]
    assert transport.forward_port is transport.manager_forward_port is None


@pytest.mark.parametrize("manager", [False, True])
@pytest.mark.parametrize("status", [401, 403, 500, 200])
def test_auto_does_not_hide_auth_or_protocol_failures(tmp_path, manager, status):
    transport, calls = forwarded_transport(tmp_path, "auto")
    transport.http = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(status, text="invalid"))
    )
    try:
        with pytest.raises(ShieldError):
            transport.manager("/api/health") if manager else transport.rpc("JSONRPC.Ping")
        assert calls == []
    finally:
        transport.close()


def test_auto_routes_each_service_independently(tmp_path):
    transport, calls = forwarded_transport(tmp_path, "auto")

    def handler(request):
        if request.url.port == 8080:
            raise httpx.ConnectError("LAN unavailable", request=request)
        if request.url.path == "/api/health":
            assert request.url.host == "192.168.0.20"
            return httpx.Response(200, json={"ok": True, "data": {}})
        return httpx.Response(200, json={"result": "pong"})

    transport.http = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        assert transport.rpc("JSONRPC.Ping") == "pong"
        assert transport.manager("/api/health") == {}
        assert calls == [("forward", "tcp:0", "tcp:8080")]
    finally:
        transport.close()


def reforwarding_transport(tmp_path, dead_ports, failure=httpx.ConnectError, route="forward"):
    """Each ``adb forward tcp:0`` hands out a new port; ``dead_ports`` lost their forward (the
    adb server restarted or the Shield slept), so a request to them fails with ``failure``."""
    transport, calls = forwarded_transport(tmp_path, route)
    ports, sent = iter(range(41234, 41300)), []

    def adb(*args, **kwargs):
        calls.append(args)
        return str(next(ports)).encode() if args[:2] == ("forward", "tcp:0") else b""

    def handler(request):
        if request.url.port == 8080 or request.url.port in dead_ports:
            raise failure("synthetic", request=request)
        sent.append((request.url.port, request.method, request.url.path))
        if request.url.path == "/jsonrpc":
            return httpx.Response(200, json={"result": "pong"})
        return httpx.Response(200, json={"ok": True, "data": {}})

    transport.adb = adb
    transport.http = httpx.Client(transport=httpx.MockTransport(handler))
    return transport, calls, sent


@pytest.mark.parametrize("route", ["forward", "auto"])
def test_lost_forward_is_reestablished_and_refused_request_retried_once(tmp_path, route):
    dead = set()
    transport, calls, sent = reforwarding_transport(tmp_path, dead, route=route)
    try:
        assert transport.rpc("JSONRPC.Ping") == "pong"
        dead.add(41234)  # adb server restarted: the forward is gone, connects are refused.
        assert transport.rpc("JSONRPC.Ping") == "pong"
        assert transport.forward_port == 41235
        assert calls == [
            ("forward", "tcp:0", "tcp:8080"),
            ("forward", "--remove", "tcp:41234"),
            ("forward", "tcp:0", "tcp:8080"),
        ]
        assert [port for port, _, _ in sent] == [41234, 41235]
    finally:
        transport.close()


def test_refused_manager_write_is_retried_once_through_a_new_forward(tmp_path):
    dead = set()
    transport, calls, sent = reforwarding_transport(tmp_path, dead)
    try:
        transport.manager("/api/health")
        dead.add(41234)
        assert transport.manager("/api/widgets/layout/rebuild", "POST", {}) == {}
        # The refused connect delivered nothing, so the write reached Kodi Manager once.
        assert sent == [
            (41234, "GET", "/api/health"),
            (41235, "POST", "/api/widgets/layout/rebuild"),
        ]
    finally:
        transport.close()


def test_retry_through_a_new_forward_happens_only_once(tmp_path):
    dead = set(range(41234, 41300))
    transport, calls, sent = reforwarding_transport(tmp_path, dead)
    try:
        with pytest.raises(ShieldError) as error:
            transport.rpc("JSONRPC.Ping")
        assert error.value.kind == "unreachable"
        assert [c for c in calls if c[:2] == ("forward", "tcp:0")] == [
            ("forward", "tcp:0", "tcp:8080")
        ] * 2
        assert sent == []
    finally:
        transport.close()


@pytest.mark.parametrize(
    "failure,manager,dropped",
    [
        # The request may have been delivered: never resend it.
        (httpx.RemoteProtocolError, False, True),
        (httpx.ReadError, False, True),
        (httpx.ReadTimeout, False, False),
        (httpx.ReadTimeout, True, False),
        (httpx.WriteError, True, False),
    ],
)
def test_failure_after_connect_is_never_retried(tmp_path, failure, manager, dropped):
    attempts = []

    def fail(message, request):
        attempts.append(request.url.port)
        if failure is httpx.RemoteProtocolError:
            return failure("Server disconnected without sending a response.", request=request)
        return failure(message, request=request)

    dead = {41234}
    transport, calls, sent = reforwarding_transport(tmp_path, dead, failure=fail)
    try:
        with pytest.raises(ShieldError) as error:
            if manager:
                transport.manager("/api/widgets/layout/rebuild", "POST", {})
            else:
                transport.rpc("Player.Stop", {"playerid": 1})
        assert attempts == [41234]
        assert (error.value.kind == "unreachable") is dropped
        if dropped:  # An unreachable forward is still dropped for the next call.
            assert transport.rpc("JSONRPC.Ping") == "pong"
            assert sent == [(41235, "POST", "/jsonrpc")]
    finally:
        transport.close()


def test_direct_failures_are_not_retried(tmp_path):
    transport, calls, sent = reforwarding_transport(tmp_path, set(), route="direct")
    try:
        with pytest.raises(ShieldError) as error:
            transport.rpc("JSONRPC.Ping")
        assert error.value.kind == "unreachable" and calls == [] and sent == []
    finally:
        transport.close()


def test_reset_forwards_after_adb_reconnect(tmp_path):
    transport, calls, sent = reforwarding_transport(tmp_path, set())
    try:
        transport.rpc("JSONRPC.Ping")
        transport.reset_forwards()
        assert transport.forward_port is None and transport._kodi_url is None
        transport.rpc("JSONRPC.Ping")
        assert [port for port, _, _ in sent] == [41234, 41235]
        assert ("forward", "--remove", "tcp:41234") in calls
    finally:
        transport.close()


def test_push_timeout_scales_with_file_size(tmp_path):
    from nvidia_mcp.transport import push_atomic

    pushes = []

    class Device:
        def adb(self, *args, **kwargs):
            pushes.append(kwargs.get("timeout"))

        def shell(self, *args, **kwargs):
            return ""

    small, large = tmp_path / "small", tmp_path / "large"
    small.write_bytes(b"x")
    with large.open("wb") as handle:
        handle.truncate(600 * 2**20)  # Sparse: 600 MiB at 1 MiB/s.
    push_atomic(Device(), small, "/sdcard/small")
    push_atomic(Device(), large, "/sdcard/large")
    push_atomic(Device(), large, "/sdcard/large", timeout=5)
    assert pushes == [120, 600, 5]


def test_http_route_configuration_and_server_use(monkeypatch, tmp_path):
    from nvidia_mcp.server import create_server

    monkeypatch.setenv("SHIELD_HOST", "127.0.0.1")
    monkeypatch.setenv("NVIDIA_MCP_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("KODI_HTTP_ROUTE", "forward")
    config = Config.from_env()
    _, ops = create_server(config)
    try:
        assert ops.t.kodi_route == "forward"
    finally:
        ops.t.close()
    monkeypatch.setenv("KODI_HTTP_ROUTE", "invalid")
    with pytest.raises(ShieldError, match="KODI_HTTP_ROUTE"):
        Config.from_env()


def test_server_failure_closes_its_transport(monkeypatch):
    from types import SimpleNamespace

    from nvidia_mcp import server

    closed = []

    def fail(**kwargs):
        raise ShieldError("Synthetic failure")

    monkeypatch.setattr("sys.argv", ["nvidia-mcp"])
    monkeypatch.setattr(server.Config, "from_env", lambda: Config(host="127.0.0.1"))
    monkeypatch.setattr(
        server,
        "create_server",
        lambda _: (
            SimpleNamespace(run=fail),
            SimpleNamespace(t=SimpleNamespace(close=lambda: closed.append(True))),
        ),
    )
    assert server.main() == 1
    assert closed == [True]


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


@pytest.mark.parametrize("manager,status", [(False, 200), (True, 500)])
def test_dripping_http_body_has_total_deadline_and_closes_stream(monkeypatch, manager, status):
    from types import SimpleNamespace

    from nvidia_mcp import transport as module

    clock, closed = [0.0], []
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: clock[0]), raising=False)
    raw = (
        b'{"result":"pong"}'
        if not manager
        else b'{"ok":false,"error":{"code":"server_error","message":"synthetic error"}}'
    )

    class Drip(httpx.SyncByteStream):
        def __iter__(self):
            for byte in raw:
                clock[0] += 0.4
                yield bytes([byte])

        def close(self):
            closed.append(True)

    transport = Transport(Config(host="127.0.0.1", manager_token="synthetic"))
    transport.response_deadline = 1.0
    transport.http.close()
    transport.http = httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(status, stream=Drip()))
    )
    try:
        with pytest.raises(ShieldError) as error:
            transport.request("http://127.0.0.1/jsonrpc", manager=manager)
        assert error.value.kind == "response_timeout" and closed
        assert clock[0] < 2.0
    finally:
        transport.close()


def test_manager_success_without_data_is_invalid_response():
    transport = manager_transport(200, {"ok": True})
    try:
        with pytest.raises(ShieldError) as error:
            transport.manager("/api/health")
        assert error.value.kind == "invalid_response"
    finally:
        transport.close()


@pytest.mark.parametrize(
    "failure,kind",
    [
        (httpx.ReadTimeout, "response_timeout"),
        (httpx.ReadError, "invalid_response"),
        (httpx.RemoteProtocolError, "invalid_response"),
    ],
)
def test_partial_response_failure_never_masquerades_as_offline(failure, kind):
    class Partial(httpx.SyncByteStream):
        def __iter__(self):
            yield b"{"
            raise failure("synthetic-private-server-detail")

    transport = Transport(Config(host="127.0.0.1", manager_token="synthetic"))
    transport.http.close()
    transport.http = httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, stream=Partial()))
    )
    try:
        with pytest.raises(ShieldError) as error:
            transport.manager("/api/portable/state")
        assert error.value.kind == kind and "synthetic-private" not in str(error.value)
    finally:
        transport.close()


@pytest.mark.parametrize(
    "message,kind",
    [
        ("illegal HTTP status line", "invalid_response"),
        ("Server disconnected without sending a response.", "unreachable"),
    ],
)
def test_header_protocol_failure_is_distinct_from_no_reply(message, kind):
    def bad_headers(request):
        raise httpx.RemoteProtocolError(message)

    transport = Transport(Config(host="127.0.0.1"))
    transport.http.close()
    transport.http = httpx.Client(transport=httpx.MockTransport(bad_headers))
    try:
        with pytest.raises(ShieldError) as error:
            transport.rpc("JSONRPC.Version")
        assert error.value.kind == kind
    finally:
        transport.close()


def test_native_http_deadline_interrupts_dripping_headers():
    import socket
    import threading
    import time

    stop, sent = threading.Event(), threading.Event()
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(3)

    def peer():
        try:
            conn, _ = listener.accept()
            with conn:
                conn.settimeout(3)
                conn.recv(4096)
                conn.sendall(b"HTTP/1.1 200 OK\r\nX-Drip: ")
                sent.set()
                while not stop.wait(0.03):
                    conn.sendall(b"x")
        except OSError:
            pass

    thread = threading.Thread(target=peer, daemon=True)
    thread.start()
    transport = Transport(Config(host="127.0.0.1"))
    transport.response_deadline = 0.5
    started = time.monotonic()
    try:
        with pytest.raises(ShieldError) as error:
            transport.request("http://127.0.0.1:%d/jsonrpc" % listener.getsockname()[1])
        assert sent.is_set() and error.value.kind == "response_timeout"
        assert time.monotonic() - started < 3
    finally:
        stop.set()
        transport.close()
        listener.close()
        thread.join(timeout=3)


def envelope(code, message):
    return {"ok": False, "code": code, "error": {"code": code, "message": message, "details": {}}}


@pytest.mark.parametrize(
    "status,code,message,kind,shown",
    [
        (403, "write_disabled", "Write Mode is disabled", "write_disabled", "Write Mode"),
        (403, "origin_mismatch", "Cross-origin request rejected", "origin_mismatch", "origin"),
        (403, "forbidden", "Non-private client rejected", "permission_denied", "rejected"),
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
