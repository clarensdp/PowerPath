"""Bounded, read-only national PermitIQ navigation and screening API.

Not accessible in required-auth mode; no project scoping or ownership is implied.
"""

from __future__ import annotations

import os
import threading
import time
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from permitting.official_gis import assess_official, remote_enabled
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, field_validator

from permitting.national import NationalScreenError, coverage, counties, screen, state_geojson

router = APIRouter()
_GIS_RATELIMIT = {}
_GIS_LOCK = threading.Lock()
ROOT = Path(__file__).resolve().parent.parent


class ScreenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    county_geoid: str | None = Field(default=None, pattern=r"^\d{5}$")
    facts: dict = Field(default_factory=dict)
    as_of: str | None = None
    proposed_scenario: bool = False

    @field_validator("facts")
    @classmethod
    def bounded_facts(cls, v):
        def check(x, level=0):
            if level > 5:
                raise ValueError("Facts exceed permitted nesting depth")
            if isinstance(x, dict):
                if len(x) > 60:
                    raise ValueError("Too many fields")
                for k, val in x.items():
                    if len(k) > 100:
                        raise ValueError("Fact key too long")
                    check(val, level + 1)
            elif isinstance(x, list):
                if len(x) > 100:
                    raise ValueError("Too many fact array items")
                for val in x:
                    check(val, level + 1)
            elif isinstance(x, str) and len(x) > 1000:
                raise ValueError("Fact value too long")

        check(v)
        return v


class GISPointRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    consent_remote: bool


def _gis_throttle(request: Request):
    """Bound public alpha GIS proxy cost to 20 requests per hour per client IP."""
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _GIS_LOCK:
        if len(_GIS_RATELIMIT) > 1000:
            for k, v in list(_GIS_RATELIMIT.items()):
                if now - v[0] > 3600:
                    _GIS_RATELIMIT.pop(k, None)
        beginning, count = _GIS_RATELIMIT.get(ip, (now, 0))
        if now - beginning > 3600:
            beginning, count = now, 0
        if count >= 20:
            raise HTTPException(429, "GIS lookup quota reached for this client")
        _GIS_RATELIMIT[ip] = (beginning, count + 1)


def install(app):
    def public_alpha():
        if os.getenv("POWERPATH_V27_AUTH_MODE") == "required":
            raise HTTPException(
                503, "National screening unavailable in required-auth mode pending scoped project access review"
            )

    @router.get("/api/permitting/coverage")
    def get_coverage(
        latitude: float = Query(ge=-90, le=90, allow_inf_nan=False),
        longitude: float = Query(ge=-180, le=180, allow_inf_nan=False),
        county_geoid: str | None = None,
    ):
        public_alpha()
        try:
            return coverage(latitude, longitude, county_geoid=county_geoid)
        except NationalScreenError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get("/api/permitting/map/states")
    def get_states():
        public_alpha()
        return state_geojson()

    @router.get("/api/permitting/counties")
    def get_counties(state_fips: str = Query(pattern=r"^\d{2}$"), q: str = Query(default="", max_length=90)):
        public_alpha()
        try:
            return counties(state_fips, q)
        except NationalScreenError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post("/api/permitting/screen")
    async def post_screen(request: Request):
        public_alpha()
        raw = await request.body()
        if len(raw) > 20000:
            raise HTTPException(413, "Screening payload too large")
        try:
            payload = ScreenRequest.model_validate_json(raw)
        except ValueError as exc:
            raise HTTPException(422, "Malformed or invalid screening request") from exc
        try:
            return screen(
                payload.latitude,
                payload.longitude,
                county_geoid=payload.county_geoid,
                facts=payload.facts,
                as_of=payload.as_of,
                proposed=payload.proposed_scenario,
            )
        except NationalScreenError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.post("/api/permitting/official-gis")
    def post_official_gis(payload: GISPointRequest, request: Request):
        public_alpha()
        if not payload.consent_remote:
            raise HTTPException(422, "Explicit consent required before contacting Census, FEMA or USFWS")
        if not remote_enabled():
            raise HTTPException(
                503, "Remote official GIS disabled by operator; set POWERPATH_PERMITIQ_REMOTE_OVERLAYS=1"
            )
        _gis_throttle(request)
        try:
            return assess_official(payload.latitude, payload.longitude, consent=True)
        except NationalScreenError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get("/api/permitting/official-gis/status")
    def get_official_gis_status():
        public_alpha()
        return {
            "enabled": remote_enabled(),
            "mode": "opt-in remote point checks",
            "coverage": "Census county/place candidates; FEMA NFHL and USFWS NWI at a single point only",
            "privacy": "Coordinates are sent to the three agencies when explicitly initiated; no results persisted",
            "limitations": "Not a parcel footprint scan or legal permit finding",
        }

    @router.get("/permitiq-national")
    def national_workspace():
        public_alpha()
        return FileResponse(
            ROOT / "web" / "public" / "permitiq-national.html",
            headers={
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
                "X-Content-Type-Options": "nosniff",
            },
        )

    app.include_router(router)
