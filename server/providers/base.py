"""Small bounded HTTP client and project-scoped persistent cache for public sources."""
from __future__ import annotations

import hashlib
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def now():
    return datetime.now(timezone.utc).isoformat()


class DataPoint(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    value: float | None = None
    unit: str
    source_name: str
    source_url: str | None = None
    retrieved_at: str
    effective_date: str | None = None
    status: Literal['observed', 'estimated', 'user_supplied', 'assumed', 'unavailable']
    methodology: str
    category: str = ''
    coverage: str = ''
    evidence_id: str | None = None

    @model_validator(mode='after')
    def missing_is_unknown(self):
        if self.value is None:
            self.status = 'unavailable'
        elif self.status == 'unavailable':
            raise ValueError('Unavailable values must be null')
        return self


class ProviderResult(BaseModel):
    provider: str
    status: Literal['available', 'partial', 'unavailable'] = 'available'
    source_url: str
    retrieved_at: str
    cached: bool = False
    points: list[DataPoint] = Field(default_factory=list)
    features: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class ProviderError(Exception):
    """Messages are safe for clients: never include credential-bearing URLs."""


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def unavailable(name, url, reason):
    return ProviderResult(provider=name, source_url=url, retrieved_at=now(),
                          status='unavailable', error=reason).model_dump()


def scrub(value):
    # NREL echoes inputs, including api_key. Never retain that field in the cache.
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()
                if k.lower() not in {'api_key', 'apikey', 'token', 'authorization', 'ocp-apim-subscription-key'}}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class PublicHTTP:
    def __init__(self, db, transport=None, sleep=time.sleep):
        self.db = db
        self.transport = transport or urllib.request.build_opener(NoRedirect()).open
        self.sleep = sleep

    def get(self, project_id, url, params=None, headers=None, ttl=86400):
        params, headers = params or {}, headers or {}
        # Credentials influence the hash (a newly configured key bypasses cached errors),
        # but neither credentials nor full request URLs are persisted or logged.
        key = hashlib.sha256(json.dumps([url, params, headers], sort_keys=True).encode()).hexdigest()
        with self.db() as con:
            row = con.execute('SELECT * FROM site_energy_cache WHERE project_id=? AND cache_key=?',
                              (project_id, key)).fetchone()
        if row and row['expires_at'] > time.time():
            if row['error']:
                raise ProviderError(row['error'])
            return json.loads(row['body']), row['retrieved_at'], True
        request = urllib.request.Request(url + '?' + urllib.parse.urlencode(params, doseq=True),
                                         headers={'Accept': 'application/json', 'User-Agent': 'PowerPath/30.8.3', **headers})
        error, payload = None, None
        for attempt in range(2):
            try:
                with self.transport(request, timeout=8) as response:
                    raw = response.read(8 * 1024 * 1024 + 1)
                if len(raw) > 8 * 1024 * 1024:
                    raise ProviderError('Provider response exceeded 8 MB limit')
                payload = json.loads(raw)
                if not isinstance(payload, dict) or payload.get('error') or payload.get('errors'):
                    raise ProviderError('Provider returned an error response')
                payload = scrub(payload)
                break
            except urllib.error.HTTPError as exc:
                error = f'Provider HTTP {exc.code}'
                if exc.code not in (429, 500, 502, 503, 504):
                    break
            except (OSError, TimeoutError):
                error = 'Provider timed out or could not be reached'
            except (ValueError, ProviderError):
                error = 'Provider returned invalid or unavailable data'
                break
            if attempt == 0:
                self.sleep(0.25)
        if payload is not None and isinstance(payload, dict) and not payload.get('error') and not payload.get('errors'):
            error = None
        else:
            payload = None
        ts = now()
        with self.db() as con:
            con.execute('''INSERT INTO site_energy_cache(project_id,cache_key,body,retrieved_at,expires_at,error)
                VALUES(?,?,?,?,?,?) ON CONFLICT(project_id,cache_key) DO UPDATE SET
                body=excluded.body,retrieved_at=excluded.retrieved_at,expires_at=excluded.expires_at,error=excluded.error''',
                (project_id, key, json.dumps(payload), ts, time.time() + (60 if error else ttl), error))
        if error:
            raise ProviderError(error)
        return payload, ts, False
