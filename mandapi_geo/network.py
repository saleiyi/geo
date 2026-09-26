"""Public-web transport: validate DNS, pin connections and enforce one deadline."""

from __future__ import annotations

import ipaddress
import re
import socket
import ssl
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from urllib.parse import urlsplit, urlunsplit

import httpcore
import httpx


class UnsafeURL(ValueError):
    """A URL cannot be safely requested by the public website scanner."""


def public_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return public_ip(str(address.ipv4_mapped))
        if address.sixtofour is not None or address.teredo is not None:
            return False
    return bool(address.is_global and not address.is_private and not address.is_loopback
                and not address.is_link_local and not address.is_reserved
                and not address.is_multicast and not address.is_unspecified)


def normalize_public_url(raw: str) -> str:
    """Validate syntax without DNS; actual connections validate every answer."""
    if not isinstance(raw, str) or not raw.strip():
        raise UnsafeURL("Informe uma URL pública válida.")
    if len(raw) > 4096 or any(ord(char) < 32 or ord(char) == 127 for char in raw):
        raise UnsafeURL("A URL contém caracteres inválidos ou é longa demais.")
    raw = raw.strip()
    if "\\" in raw:
        raise UnsafeURL("A URL contém caracteres inválidos.")
    if raw.startswith("//"):
        raw = "https:" + raw
    elif not re.match(r"^https?://", raw, re.IGNORECASE):
        if "://" in raw or re.match(r"^(?:file|data|javascript|mailto|ftp):", raw, re.I):
            raise UnsafeURL("Use uma URL pública com http:// ou https://.")
        raw = "https://" + raw
    try:
        parsed = urlsplit(raw)
        host = parsed.hostname or ""
        port = parsed.port
    except ValueError as exc:
        raise UnsafeURL("Informe uma URL pública válida.") from exc
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeURL("Use uma URL pública com http:// ou https://.")
    if "@" in parsed.netloc or parsed.username is not None or parsed.password is not None:
        raise UnsafeURL("URLs com usuário ou senha não são permitidas.")
    if not host or "%" in host or any(char.isspace() for char in host) or port == 0:
        raise UnsafeURL("Informe um endereço público válido.")
    host = host.rstrip(".").lower()
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not public_ip(host):
            raise UnsafeURL("Endereços locais, privados ou reservados não são permitidos.")
        host = f"[{host}]" if literal.version == 6 else host
    else:
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise UnsafeURL("Informe um domínio válido.") from exc
        labels = host.split(".")
        if (len(host) > 253 or len(labels) < 2
            or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)
            or host.endswith((".localhost", ".local", ".internal", ".lan", ".home", ".test", ".invalid"))):
            raise UnsafeURL("Informe um domínio público válido.")
    authority = host + (f":{port}" if port is not None else "")
    candidate = urlunsplit((parsed.scheme.lower(), authority, parsed.path or "/", parsed.query, ""))
    try:
        return str(httpx.URL(candidate))
    except httpx.InvalidURL as exc:
        raise UnsafeURL("Informe uma URL pública válida.") from exc


def remaining(deadline: float, timeout: float | None = None) -> float:
    available = deadline - time.monotonic()
    if available <= 0:
        raise httpcore.ReadTimeout("Request deadline exceeded")
    return min(available, timeout) if timeout is not None else available


# Bound DNS wait time and outstanding OS lookups, including timed-out jobs.
_DNS_WORKERS = 8
_DNS_POOL = ThreadPoolExecutor(max_workers=_DNS_WORKERS, thread_name_prefix="geo-dns")
_DNS_SLOTS = threading.BoundedSemaphore(_DNS_WORKERS)


def resolve_public(host: str, port: int, deadline: float) -> list[tuple]:
    if not _DNS_SLOTS.acquire(timeout=remaining(deadline)):
        raise httpcore.ConnectTimeout("DNS deadline exceeded")
    try:
        future = _DNS_POOL.submit(socket.getaddrinfo, host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except Exception:
        _DNS_SLOTS.release()
        raise
    future.add_done_callback(lambda _future: _DNS_SLOTS.release())
    try:
        answers = future.result(timeout=remaining(deadline))
    except FutureTimeout as exc:
        future.cancel()
        raise httpcore.ConnectTimeout("DNS deadline exceeded") from exc
    except OSError as exc:
        raise httpcore.ConnectError("DNS resolution failed") from exc
    remaining(deadline)
    if not answers or any(not public_ip(answer[4][0]) for answer in answers):
        raise UnsafeURL("O domínio aponta para um endereço local, privado ou reservado.")
    return answers


class DeadlineStream(httpcore.NetworkStream):
    def __init__(self, stream: httpcore.NetworkStream, deadline: float) -> None:
        self.stream = stream
        self.deadline = deadline

    def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        result = self.stream.read(max_bytes, remaining(self.deadline, timeout))
        remaining(self.deadline)
        return result

    def write(self, buffer: bytes, timeout: float | None = None) -> None:
        self.stream.write(buffer, remaining(self.deadline, timeout))
        remaining(self.deadline)

    def start_tls(self, ssl_context: ssl.SSLContext, server_hostname: str | None = None,
                  timeout: float | None = None) -> DeadlineStream:
        # httpcore retains the origin hostname for TLS SNI/certificate checks.
        wrapped = self.stream.start_tls(ssl_context, server_hostname, remaining(self.deadline, timeout))
        return DeadlineStream(wrapped, self.deadline)

    def get_extra_info(self, info: str):
        return self.stream.get_extra_info(info)

    def close(self) -> None:
        self.stream.close()


class PublicNetworkBackend(httpcore.SyncBackend):
    def __init__(self, deadline: float) -> None:
        self.deadline = deadline

    def connect_tcp(self, host: str, port: int, timeout: float | None = None,
                    local_address: str | None = None, socket_options=None) -> httpcore.NetworkStream:
        answers = resolve_public(host, port, self.deadline)
        last_error: Exception | None = None
        # Only vetted numeric sockaddrs are used, without resolving host again.
        for family, socktype, proto, _canonname, sockaddr in answers:
            sock = socket.socket(family, socktype, proto)
            try:
                sock.settimeout(remaining(self.deadline, timeout))
                for option in socket_options or ():
                    sock.setsockopt(*option)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                if local_address is not None:
                    sock.bind((local_address, 0))
                sock.connect(sockaddr)
                from httpcore._backends.sync import SyncStream
                return DeadlineStream(SyncStream(sock), self.deadline)
            except (OSError, httpcore.TimeoutException) as exc:
                sock.close()
                last_error = exc
        if isinstance(last_error, (socket.timeout, httpcore.TimeoutException)):
            raise httpcore.ConnectTimeout("Connection deadline exceeded") from last_error
        raise httpcore.ConnectError("Connection failed") from last_error


class PublicHTTPTransport(httpx.HTTPTransport):
    def __init__(self, deadline: float) -> None:
        # Reuse HTTPTransport's request/exception adapters with our own backend.
        super().__init__(trust_env=False)
        self._pool.close()
        self._pool = httpcore.ConnectionPool(
            ssl_context=ssl.create_default_context(),
            network_backend=PublicNetworkBackend(deadline),
            max_keepalive_connections=0,
            retries=0,
        )
