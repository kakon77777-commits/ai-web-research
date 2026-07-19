"""SSRF guard: reject requests to loopback/private/link-local/metadata hosts.

Applied before every fetch. DNS resolution happens here so that DNS
rebinding between the check and the actual request is the only residual
risk, which is acceptable for a single-operator research crawler.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

_METADATA_IPS = {"169.254.169.254"}


class SSRFBlockedError(Exception):
    pass


class SSRFGuard:
    def __init__(
        self,
        block_private_networks: bool = True,
        allow_localhost: bool = False,
        allow_file_scheme: bool = False,
    ):
        self.block_private_networks = block_private_networks
        self.allow_localhost = allow_localhost
        self.allow_file_scheme = allow_file_scheme

    async def check(self, url: str) -> None:
        parsed = urlparse(url)

        if parsed.scheme == "file":
            if self.allow_file_scheme:
                return
            raise SSRFBlockedError(f"file:// scheme blocked: {url}")

        if parsed.scheme not in ("http", "https"):
            raise SSRFBlockedError(f"unsupported scheme: {url}")

        host = parsed.hostname
        if not host:
            raise SSRFBlockedError(f"no hostname in url: {url}")

        if host.lower() == "localhost" and not self.allow_localhost:
            raise SSRFBlockedError(f"localhost blocked: {url}")

        try:
            infos = await asyncio.to_thread(socket.getaddrinfo, host, None)
        except socket.gaierror as exc:
            raise SSRFBlockedError(f"DNS resolution failed for {host}: {exc}") from exc

        for info in infos:
            ip_str = info[4][0]
            if ip_str in _METADATA_IPS:
                raise SSRFBlockedError(f"cloud metadata IP blocked: {ip_str} ({url})")

            ip = ipaddress.ip_address(ip_str)
            if ip.is_loopback:
                if self.allow_localhost:
                    continue
                raise SSRFBlockedError(f"loopback IP blocked: {ip_str} ({url})")

            if not self.block_private_networks:
                continue
            if ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise SSRFBlockedError(f"private/reserved IP blocked: {ip_str} ({url})")
