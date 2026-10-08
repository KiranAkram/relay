"""Visitor identity for the demo limits: a signed, long-lived cookie.

The demo doctor login is shared, so limits cannot hang off the account. A
random id is issued on first upload and signed with SECRET_KEY; a forged or
tampered cookie is simply replaced. Clearing cookies gives a new id, which is
why the IP address is counted as well.
"""

import hmac
import secrets
from hashlib import sha256

from fastapi import Request, Response

from app.core.config import settings

COOKIE_NAME = "relay_visitor"
COOKIE_MAX_AGE = 365 * 24 * 3600


def _sign(visitor_id: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(), visitor_id.encode(), sha256
    ).hexdigest()[:32]


def visitor_id(request: Request, response: Response) -> str:
    """Return the visitor id from a valid cookie, or issue a new one."""
    raw = request.cookies.get(COOKIE_NAME, "")
    candidate, _, signature = raw.partition(".")
    if candidate and hmac.compare_digest(signature, _sign(candidate)):
        return candidate
    fresh = secrets.token_urlsafe(16)
    response.set_cookie(
        COOKIE_NAME,
        f"{fresh}.{_sign(fresh)}",
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )
    return fresh


def client_ip(request: Request) -> str:
    """Client address, honouring the first X-Forwarded-For hop behind a proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "unknown")[:64]
