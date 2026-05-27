"""Auth0 JWT verification dependency."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from api.settings import settings

logger = logging.getLogger(__name__)

_jwks_cache: dict[str, Any] = {}
_jwks_fetched_at: float = 0.0
_JWKS_TTL = 3600.0

security = HTTPBearer()


async def _get_jwks() -> dict[str, Any]:
    """Fetch and cache the Auth0 JWKS public keys."""
    global _jwks_fetched_at, _jwks_cache  # noqa: PLW0603

    now = time.monotonic()
    if _jwks_cache and now - _jwks_fetched_at < _JWKS_TTL:
        return _jwks_cache

    url = f"https://{settings.auth0_domain}/.well-known/jwks.json"
    logger.debug("Fetching JWKS from %s", url)
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        _jwks_cache = response.json()
        _jwks_fetched_at = now
        logger.debug("JWKS fetched, %d keys", len(_jwks_cache.get("keys", [])))
        return _jwks_cache


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> dict[str, Any]:
    """Validate a Bearer JWT issued by Auth0 and return the payload.

    :param credentials: Bearer token from Authorization header.
    :return: Decoded JWT payload with user claims.
    :raises HTTPException: 401 if the token is missing, expired, or invalid.
    """
    token = credentials.credentials
    try:
        jwks = await _get_jwks()
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        alg = unverified_header.get("alg")
        logger.debug("Token header — kid=%s alg=%s", kid, alg)

        rsa_key: dict[str, str] = {}
        available_kids = [k.get("kid") for k in jwks.get("keys", [])]
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "n": key["n"],
                    "e": key["e"],
                }
                break

        if not rsa_key:
            logger.error(
                "No matching JWKS key — token kid=%s available kids=%s domain=%s",
                kid,
                available_kids,
                settings.auth0_domain,
            )
            raise HTTPException(status_code=401, detail="Invalid token key")

        payload: dict[str, Any] = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=settings.auth0_audience,
            issuer=f"https://{settings.auth0_domain}/",
        )
        return payload

    except httpx.HTTPError as exc:
        logger.error(
            "Failed to fetch JWKS — domain=%s error=%s", settings.auth0_domain, exc
        )
        raise HTTPException(status_code=503, detail="Auth service unavailable") from exc
    except JWTError as exc:
        logger.error(
            "JWT validation failed — error=%s domain=%s audience=%s",
            exc,
            settings.auth0_domain,
            settings.auth0_audience,
        )
        raise HTTPException(status_code=401, detail="Invalid token") from exc
