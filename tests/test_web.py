"""Exercise the fetch boundary with HTTPX's transport, without real public requests."""

import asyncio
import gzip
import socket
from hashlib import sha256

import httpx
import pytest

from app.errors import NexusError
from app.jobs import web


@pytest.fixture
def web_http(monkeypatch):
    requests = []

    def install(handler, addresses=("93.184.216.34",)):
        monkeypatch.setattr(
            socket,
            "getaddrinfo",
            lambda *args, **kwargs: [
                (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, 443))
                for address in addresses
            ],
        )

        async def respond(request):
            requests.append(request)
            response = handler(request)
            return await response if asyncio.iscoroutine(response) else response

        monkeypatch.setattr(
            web.safehttpx, "AsyncSecureTransport", lambda address: httpx.MockTransport(respond)
        )
        return requests

    return install


@pytest.mark.parametrize("address", ["127.0.0.1", "169.254.169.254", "10.0.0.1", "::1"])
def test_private_dns_is_denied_before_connecting(settings, web_http, address):
    requests = web_http(lambda request: httpx.Response(200), ("93.184.216.34", address))
    with pytest.raises(NexusError, match="non-public address"):
        asyncio.run(web.fetch_public_page("https://example.com", ["example.com"], settings))
    assert requests == []


@pytest.mark.parametrize(
    "target", ["https://unapproved.com", "http://example.com", "https://127.0.0.1"]
)
def test_every_redirect_is_checked(settings, web_http, target):
    requests = web_http(lambda request: httpx.Response(302, headers={"location": target}))
    with pytest.raises(NexusError) as error:
        asyncio.run(web.fetch_public_page("https://example.com", ["example.com"], settings))
    assert error.value.code == "WEB_FETCH_DENIED"
    assert len(requests) == 1


def test_redirect_loop_is_bounded(settings, web_http):
    requests = web_http(lambda request: httpx.Response(302, headers={"location": "/loop"}))
    with pytest.raises(NexusError, match="redirect limit"):
        asyncio.run(web.fetch_public_page("https://example.com", ["example.com"], settings))
    assert len(requests) == 4


def test_html_extraction_preserves_hash_and_final_url(settings, web_http):
    html = (
        b"<html><head><title>Alpha retention</title></head><body><article>"
        b"<h1>Alpha retention</h1><p>Alpha retains records for thirty days. "
        b"Requests execute synchronously before returning to the client. "
        b"This policy describes the local research system.</p></article>"
        b"<script>window.evil = true;</script></body></html>"
    )

    def response(request):
        if request.url.path != "/policy":
            return httpx.Response(302, headers={"location": "/policy#retention"})
        return httpx.Response(200, headers={"content-type": "text/html"}, content=html)

    requests = web_http(response)
    snapshot = asyncio.run(web.fetch_public_page("https://example.com", ["example.com"], settings))
    assert len(requests) == 2
    assert snapshot.final_url == "https://example.com/policy"
    assert snapshot.content_sha256 == sha256(html).hexdigest()
    assert "thirty days" in snapshot.text and "window.evil" not in snapshot.text


@pytest.mark.parametrize("content_type", ["application/pdf", "application/octet-stream"])
def test_unsupported_content_is_rejected(settings, web_http, content_type):
    web_http(lambda request: httpx.Response(200, headers={"content-type": content_type}))
    with pytest.raises(NexusError) as error:
        asyncio.run(web.fetch_public_page("https://example.com", ["example.com"], settings))
    assert error.value.code == "WEB_CONTENT_UNSUPPORTED"


def test_response_byte_limit(settings, web_http):
    web_http(
        lambda request: httpx.Response(
            200, headers={"content-type": "text/plain"}, content=b"too much text"
        )
    )
    with pytest.raises(NexusError) as error:
        asyncio.run(
            web.fetch_public_page(
                "https://example.com",
                ["example.com"],
                settings.model_copy(update={"max_web_bytes": 5}),
            )
        )
    assert error.value.code == "WEB_CONTENT_TOO_LARGE"


def test_server_cannot_force_unbounded_decompression(settings, web_http):
    web_http(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "text/plain", "content-encoding": "gzip"},
            content=gzip.compress(b"compressed content"),
        )
    )
    with pytest.raises(NexusError) as error:
        asyncio.run(web.fetch_public_page("https://example.com", ["example.com"], settings))
    assert error.value.code == "WEB_CONTENT_UNSUPPORTED"


def test_entire_fetch_has_a_deadline(settings, web_http):
    async def slow_response(request):
        await asyncio.sleep(1)
        return httpx.Response(200, headers={"content-type": "text/plain"}, text="late")

    web_http(slow_response)
    with pytest.raises(NexusError) as error:
        asyncio.run(
            web.fetch_public_page(
                "https://example.com",
                ["example.com"],
                settings.model_copy(update={"web_timeout_seconds": 0.02}),
            )
        )
    assert error.value.code == "WEB_FETCH_TIMEOUT" and error.value.retryable


@pytest.mark.parametrize("status, retryable", [(404, False), (429, True), (503, True)])
def test_http_error_retry_classification(settings, web_http, status, retryable):
    web_http(lambda request: httpx.Response(status))
    with pytest.raises(NexusError) as error:
        asyncio.run(web.fetch_public_page("https://example.com", ["example.com"], settings))
    assert error.value.code == "WEB_FETCH_FAILED"
    assert error.value.retryable == retryable
