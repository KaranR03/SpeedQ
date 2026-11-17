"""Same-origin browser protections and optional staff authentication.

The unauthenticated default is for a loopback-only, synthetic-data demo. Set
NRY_STAFF_PASSWORD or NRY_STAFF_ACCOUNTS and serve over HTTPS for remote access.
"""
import base64
import binascii
import hmac
import os
import json

from fastapi import Request
from fastapi.responses import JSONResponse

DEMO_OFFICERS = ("Demo officer", "Alex Morgan", "Taylor Lee")


def auth_enabled():
    return bool(os.environ.get("NRY_STAFF_PASSWORD") or os.environ.get("NRY_STAFF_ACCOUNTS", "").strip())


def _staff_identity(request):
    password = os.environ.get("NRY_STAFF_PASSWORD", "")
    if not auth_enabled():
        demo = request.headers.get("x-demo-officer")
        default = os.environ.get("NRY_OFFICER", "Demo officer")
        return demo if demo in (*DEMO_OFFICERS, default) else None if demo else default
    username = os.environ.get("NRY_STAFF_USER", "officer")
    try:
        scheme, encoded = request.headers.get("authorization", "").split(" ", 1)
        if scheme.lower() != "basic":
            return None
        supplied_user, supplied_password = base64.b64decode(encoded, validate=True).decode("utf-8").split(":", 1)
    except (ValueError, UnicodeError, binascii.Error):
        return None
    configured = os.environ.get("NRY_STAFF_ACCOUNTS", "").strip()
    if configured:
        try:
            accounts = json.loads(configured)
            if not isinstance(accounts, dict) or not 1 <= len(accounts) <= 50 or any(
                not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v
                for k, v in accounts.items()):
                return None
        except (ValueError, TypeError):
            return None
        expected = accounts.get(supplied_user)
        valid = hmac.compare_digest(supplied_password.encode(), (expected or "unavailable-account").encode())
        return supplied_user if expected is not None and valid else None
    user_ok = hmac.compare_digest(supplied_user.encode(), username.encode())
    password_ok = hmac.compare_digest(supplied_password.encode(), password.encode())
    return username if user_ok and password_ok else None


async def browser_security(request: Request, call_next):
    write = request.method not in ("GET", "HEAD", "OPTIONS")
    # The voice webhook is a server-to-server integration, authenticated separately.
    webhook = request.url.path == "/webhook/retell" and request.method == "POST"
    secret_intake = request.url.path == "/case" and request.method == "POST" and bool(
        os.environ.get("NRY_WEBHOOK_SECRET"))
    draft_intake = request.url.path.startswith("/intake/drafts") and request.method == "POST" and bool(
        os.environ.get("NRY_WEBHOOK_SECRET"))
    origin = request.headers.get("origin")
    trusted_origins = {item.strip() for item in os.environ.get("NRY_CORS_ORIGINS", "").split(",")
                       if item.strip() and item.strip() != "*"}
    trusted_origin = origin in trusted_origins
    same_origin = not origin or origin == f"{request.url.scheme}://{request.url.netloc}" or trusted_origin
    local_client = request.client and request.client.host in ("127.0.0.1", "::1", "testclient")
    if not auth_enabled() and not local_client and not webhook and not secret_intake and not draft_intake:
        response = JSONResponse({"detail": "Local demo only. Configure staff authentication for remote access."},
                                status_code=403)
    elif write and (not same_origin or (request.headers.get("sec-fetch-site") == "cross-site" and not trusted_origin)):
        response = JSONResponse({"detail": "Cross-origin changes are not allowed."}, status_code=403)
    else:
        actor = _staff_identity(request)
        # Intake can use the existing webhook secret instead of staff credentials.
        if actor is None and not webhook and not secret_intake and not draft_intake:
            response = JSONResponse({"detail": "Staff sign-in required."}, status_code=401,
                                    headers={"WWW-Authenticate": 'Basic realm="Westpac SpeedQ", charset="UTF-8"'})
        else:
            request.state.staff_actor = actor
            response = await call_next(request)
    response.headers.update({
        "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; "
                                   "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
                                   "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cache-Control": "no-store",
    })
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    # Only the two child pages of the existing local demo may be framed by this origin.
    if request.url.path in ("/officer", "/customer"):
        response.headers["Content-Security-Policy"] = response.headers["Content-Security-Policy"].replace(
            "frame-ancestors 'none'", "frame-ancestors 'self'")
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response


def actor(request, claimed):
    """Use the authenticated identity in audit entries, never a body-supplied name."""
    return request.state.staff_actor if auth_enabled() or request.headers.get("x-demo-officer") else claimed
