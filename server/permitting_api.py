"""v30.4-alpha read-only permitting assessment API. No database writes; no financial engine changes."""

import json
import os
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()
MAX_BODY = 100_000


def install(app):
    @router.post("/api/permitting/assess")
    async def assess_project(request: Request):
        if os.getenv("POWERPATH_V27_AUTH_MODE") == "required":
            raise HTTPException(
                503, "Permitting API unavailable in authenticated/multi-tenant mode pending access-control review"
            )
        raw = await request.body()
        if len(raw) > MAX_BODY:
            raise HTTPException(413, "Project description too large")
        try:
            project = json.loads(raw)
        except ValueError as exc:
            raise HTTPException(422, "Body must be JSON") from exc
        from permitting import assess, public

        try:
            return public(assess(project))
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(422, str(exc)) from exc

    app.include_router(router)
