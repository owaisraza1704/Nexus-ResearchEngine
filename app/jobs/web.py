"""Opt-in public URL acquisition. No search-provider account or unrestricted browsing."""

import asyncio
import ipaddress
import json
import socket
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import urljoin

import httpx
import safehttpx
import trafilatura

from app.config import Settings
from app.errors import NexusError
from app.jobs.contracts import SourcePolicy


def validate_public_url(value: str, allowed_domains: list[str]) -> httpx.URL:
    try:
        url = httpx.URL(value)
    except httpx.InvalidURL as exc:
        raise NexusError("WEB_FETCH_DENIED", "The web URL is invalid.") from exc
    if (
        url.scheme != "https"
        or url.port not in {None, 443}
        or url.userinfo
        or not url.host
        or url.host.lower() not in allowed_domains
        or url.host == "localhost"
        or url.host.endswith((".localhost", ".local"))
    ):
        raise NexusError(
            "WEB_FETCH_DENIED", "Use an HTTPS URL on an explicitly approved public domain."
        )
    try:
        address = ipaddress.ip_address(url.host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise NexusError(
            "WEB_FETCH_DENIED", "Private and special-purpose addresses are not allowed."
        )
    return url.copy_with(fragment=None)


def validate_web_policy(policy: SourcePolicy, settings: Settings) -> None:
    if policy.web_urls and not policy.allow_web:
        raise NexusError("POLICY_DENIED", "Approve web acquisition before providing web URLs.")
    if len(policy.web_urls) > settings.max_web_sources:
        raise NexusError("POLICY_DENIED", "Too many approved web sources.")
    if len(policy.web_urls) != len(set(policy.web_urls)):
        raise NexusError("POLICY_DENIED", "Provide distinct web URLs.")
    if any(
        domain != domain.lower().strip() or "/" in domain or "*" in domain or "@" in domain
        for domain in policy.allowed_domains
    ):
        raise NexusError(
            "POLICY_DENIED", "Domains must be exact lowercase hostnames, not patterns."
        )
    for value in policy.web_urls:
        validate_public_url(value, policy.allowed_domains)


@dataclass(frozen=True)
class WebSnapshot:
    url: str
    final_url: str
    title: str
    text: str
    content_sha256: str
    content_type: str


async def fetch_public_page(
    url: str, allowed_domains: list[str], settings: Settings
) -> WebSnapshot:
    """Reuse SafeHTTPX's pinned-IP transport with HTTPX streaming and a total deadline.

    SafeHTTPX.get buffers whole responses and may use a third-party DNS fallback.
    We use its transport directly: local DNS, exact-domain policy, bounded streaming,
    and validation at every redirect. No document/question text is sent in a search query.
    """
    current = url
    try:
        async with asyncio.timeout(settings.web_timeout_seconds):
            for _ in range(4):
                parsed = validate_public_url(current, allowed_domains)
                resolved = await asyncio.get_running_loop().getaddrinfo(
                    parsed.host, 443, type=socket.SOCK_STREAM
                )
                addresses = list(dict.fromkeys(item[4][0] for item in resolved))
                if not addresses or any(
                    not safehttpx.is_public_ip(address)
                    or not ipaddress.ip_address(address).is_global
                    for address in addresses
                ):
                    raise NexusError(
                        "WEB_FETCH_DENIED", "The approved domain resolved to a non-public address."
                    )
                transport = safehttpx.AsyncSecureTransport(addresses[0])
                async with httpx.AsyncClient(
                    transport=transport, trust_env=False, timeout=settings.web_timeout_seconds
                ) as client:
                    async with client.stream(
                        "GET",
                        str(parsed),
                        headers={
                            "User-Agent": "NexusLocalResearch/0.1",
                            "Accept": "text/html,text/plain",
                            "Accept-Encoding": "identity",
                        },
                    ) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get("location")
                            if not location:
                                raise NexusError(
                                    "WEB_FETCH_FAILED", "The web redirect had no target."
                                )
                            current = urljoin(str(parsed), location)
                            continue
                        response.raise_for_status()
                        content_type = (
                            response.headers.get("content-type", "").split(";")[0].lower()
                        )
                        if content_type not in {"text/html", "text/plain", "application/xhtml+xml"}:
                            raise NexusError(
                                "WEB_CONTENT_UNSUPPORTED",
                                "Web acquisition supports HTML or text pages.",
                            )
                        if (
                            response.headers.get("content-encoding", "identity").lower()
                            != "identity"
                        ):
                            raise NexusError(
                                "WEB_CONTENT_UNSUPPORTED",
                                "The server ignored the uncompressed-content request.",
                            )
                        body = bytearray()
                        async for part in response.aiter_bytes(chunk_size=32_768):
                            if len(body) + len(part) > settings.max_web_bytes:
                                raise NexusError(
                                    "WEB_CONTENT_TOO_LARGE", "The web page exceeds the byte limit."
                                )
                            body.extend(part)
                        raw = bytes(body)
                        decoded = raw.decode(response.encoding or "utf-8", errors="replace")
                        if content_type == "text/plain":
                            extracted, title = decoded.strip(), parsed.host
                        else:
                            extracted_json = trafilatura.extract(
                                decoded,
                                url=str(parsed),
                                output_format="json",
                                with_metadata=True,
                                include_comments=False,
                                favor_recall=True,
                            )
                            metadata = json.loads(extracted_json) if extracted_json else {}
                            extracted = metadata.get("text", "")
                            title = metadata.get("title") or parsed.host
                        if not extracted.strip():
                            raise NexusError(
                                "WEB_CONTENT_EMPTY", "No readable text was found on the web page."
                            )
                        if len(extracted) > settings.max_document_chars:
                            raise NexusError(
                                "WEB_CONTENT_TOO_LARGE",
                                "Extracted web text exceeds the text limit.",
                            )
                        return WebSnapshot(
                            url=url,
                            final_url=str(parsed),
                            title=title[:200],
                            text=extracted,
                            content_sha256=sha256(raw).hexdigest(),
                            content_type=content_type,
                        )
            raise NexusError("WEB_FETCH_DENIED", "The web page exceeded the redirect limit.")
    except (TimeoutError, httpx.TimeoutException) as exc:
        raise NexusError(
            "WEB_FETCH_TIMEOUT", "The approved web page timed out.", 504, retryable=True
        ) from exc
    except (httpx.HTTPError, OSError) as exc:
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        raise NexusError(
            "WEB_FETCH_FAILED",
            "The approved web page could not be retrieved.",
            502,
            retryable=status is None or status == 429 or status >= 500,
        ) from exc
