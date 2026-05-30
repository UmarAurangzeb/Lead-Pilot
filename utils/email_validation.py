"""
Email deliverability + fallback helpers.

`has_mx`   — DNS MX lookup, cached per domain
`mx_filter` — drop addresses whose domain has no MX record
`fallback_emails_for_website` — synthesise common addresses (info@, contact@, …)
  at a lead's own domain, MX-verified
"""
from __future__ import annotations

import re
from functools import lru_cache
from urllib.parse import urlparse

import dns.resolver
import dns.exception

_FALLBACK_LOCAL_PARTS = ("info", "contact", "hello", "sales", "admin", "office")

# Public mailbox providers — never synthesise fallbacks against these
_PUBLIC_PROVIDERS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "ymail.com",
    "hotmail.com", "outlook.com", "live.com", "msn.com", "aol.com",
    "icloud.com", "me.com", "mac.com", "protonmail.com", "proton.me",
    "gmx.com", "gmx.net", "zoho.com", "yandex.com", "mail.com",
}

_resolver = dns.resolver.Resolver()
_resolver.lifetime = 4.0
_resolver.timeout = 4.0


@lru_cache(maxsize=2048)
def has_mx(domain: str) -> bool:
    domain = (domain or "").strip().lower().rstrip(".")
    if not domain or "." not in domain:
        return False
    try:
        answers = _resolver.resolve(domain, "MX")
        return any(str(r.exchange).strip(".") for r in answers)
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN,
            dns.resolver.NoNameservers, dns.exception.DNSException):
        return False


def mx_filter(emails: list[str]) -> list[str]:
    out = []
    for e in emails:
        if "@" not in e:
            continue
        domain = e.rsplit("@", 1)[1].lower()
        if has_mx(domain):
            out.append(e)
    return out


_DOMAIN_RE = re.compile(r"^[a-z0-9.\-]+$")


def domain_from_website(website: str | None) -> str | None:
    if not website:
        return None
    raw = website.strip()
    if not re.match(r"^https?://", raw, re.I):
        raw = f"https://{raw}"
    try:
        host = urlparse(raw).hostname or ""
    except ValueError:
        return None
    host = host.lower().lstrip(".")
    if host.startswith("www."):
        host = host[4:]
    if not host or not _DOMAIN_RE.match(host) or "." not in host:
        return None
    if host in _PUBLIC_PROVIDERS:
        return None
    return host


def fallback_emails_for_website(website: str | None) -> list[str]:
    """Synthesise `info@domain`-style addresses and keep only the MX-valid ones."""
    domain = domain_from_website(website)
    if not domain:
        return []
    if not has_mx(domain):
        return []
    return [f"{local}@{domain}" for local in _FALLBACK_LOCAL_PARTS]
