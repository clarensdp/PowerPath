"""Managed identity adapter; authorization comes only from stored memberships."""

import asyncio
import hashlib
import json
import os
import re
import urllib.request
import urllib.error
from uuid import UUID
from fastapi import HTTPException
from fastapi.responses import JSONResponse


def enabled():
    return os.environ.get("POWERPATH_IDENTITY_PROVIDER") == "supabase"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def auth_request(path, token=None, payload=None):
    base = os.environ.get("POWERPATH_SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("POWERPATH_SUPABASE_PUBLISHABLE_KEY", "")
    if not re.fullmatch(r"https://[a-z0-9]+\.supabase\.co", base) or not key.startswith("sb_publishable_"):
        raise HTTPException(503, "Managed identity configuration unavailable")
    headers = {"apikey": key, "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(
        base + "/auth/v1/" + path,
        headers=headers,
        data=json.dumps(payload).encode() if payload is not None else None,
        method="POST" if payload is not None or path.startswith("logout") else "GET",
    )
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=10) as response:
            raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ValueError("oversized response")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise HTTPException(
            401 if exc.code in (400, 401, 403, 422) else 503,
            "Authentication rejected" if exc.code in (400, 401, 403, 422) else "Identity service unavailable",
        ) from None
    except (OSError, ValueError):
        raise HTTPException(503, "Identity service unavailable") from None


def verified_user(token):
    # /user validates the bearer with Supabase; never trust decoded JWT contents
    # or user-editable metadata to grant a tenant, role or user identity.
    data = auth_request("user", token)
    try:
        identifier = str(UUID(data["id"]))
        if not data.get("email_confirmed_at") or data.get("is_anonymous"):
            raise ValueError("unconfirmed or anonymous")
        return {"id": identifier, "email": str(data.get("email", ""))}
    except (ValueError, KeyError, TypeError):
        raise HTTPException(401, "Confirmed named identity required") from None


async def gate(request, call_next, db):
    from server.institutional import ACTOR, TENANT, ROLE_RANK, MUTATE

    path = request.url.path
    if path == "/api/health" or path == "/api/v27/auth/login" or not path.startswith("/api/"):
        return await call_next(request)
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer ") or len(header) > 16384:
        return JSONResponse({"detail": "Bearer token required"}, status_code=401)
    try:
        user = await asyncio.to_thread(verified_user, header[7:])
    except HTTPException as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
    actor_token = ACTOR.set(user["id"])
    tenant_token = TENANT.set(None)
    try:
        with db() as con:
            provisioned = con.execute("SELECT id FROM v27_users WHERE id=? AND active=1", (user["id"],)).fetchone()
            if not provisioned:
                return JSONResponse({"detail": "Application access has not been provisioned"}, status_code=403)
            denied = con.execute(
                "SELECT token_hash FROM v27_sessions WHERE token_hash=? AND user_id=? AND revoked=1",
                (hashlib.sha256(header[7:].encode()).hexdigest(), user["id"]),
            ).fetchone()
            if denied:
                return JSONResponse({"detail": "Session revoked"}, status_code=401)
            members = [
                dict(r)
                for r in con.execute("SELECT tenant_id,role FROM v27_memberships WHERE user_id=?", (user["id"],))
            ]
            request.state.user_id = user["id"]
            request.state.email = user["email"]
            request.state.members = members
            match = re.match(r"^/api/projects/([^/]+)(?:/|$)", path)
            if match:
                tenant = con.execute(
                    "SELECT tenant_id FROM v27_project_tenants WHERE project_id=?", (match[1],)
                ).fetchone()
                minimum = (
                    3
                    if ("/approvals" in path or re.search(r"/intelligence/proposals/[^/]+/(approve|reject)$", path))
                    else (2 if request.method in MUTATE else 1)
                )
                member = next(
                    (
                        m
                        for m in members
                        if tenant and m["tenant_id"] == tenant["tenant_id"] and ROLE_RANK.get(m["role"], 0) >= minimum
                    ),
                    None,
                )
                if not member:
                    return JSONResponse({"detail": "Project access denied"}, status_code=403)
                request.state.tenant_id = member["tenant_id"]
                request.state.role = member["role"]
                TENANT.set(member["tenant_id"])
            elif path == "/api/projects" and request.method in MUTATE:
                chosen = request.headers.get("x-powerpath-tenant", "")
                member = next(
                    (m for m in members if m["tenant_id"] == chosen and ROLE_RANK.get(m["role"], 0) >= 2), None
                )
                if not member:
                    return JSONResponse({"detail": "Authorized X-PowerPath-Tenant required"}, status_code=403)
                request.state.tenant_id = chosen
                request.state.role = member["role"]
                TENANT.set(chosen)
            elif request.method in MUTATE and path != "/api/v27/auth/logout":
                # Global source management requires a separate operator flow.
                return JSONResponse({"detail": "Global mutation requires an operator"}, status_code=403)
        return await call_next(request)
    finally:
        ACTOR.reset(actor_token)
        TENANT.reset(tenant_token)
