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
