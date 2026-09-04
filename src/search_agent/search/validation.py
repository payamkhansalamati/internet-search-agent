import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeURL(ValueError):
    pass


def validate_url(url: str, approved_domains: set[str], *, resolve_dns: bool = True) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise UnsafeURL("Only credential-free HTTPS URLs are allowed")
    host = parsed.hostname.rstrip(".").casefold()
    if not any(host == domain or host.endswith(f".{domain}") for domain in approved_domains):
        raise UnsafeURL("Host is not an approved company domain")
    if resolve_dns:
        for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
            address = ipaddress.ip_address(info[4][0])
            if not address.is_global:
                raise UnsafeURL("Host resolves to a non-public address")
    return url
