"""Integration DAO with credential encryption."""

from __future__ import annotations

import json
from typing import Any

from cryptography.fernet import Fernet
from fastapi import Depends
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.dependencies import get_db_session
from api.db.models.integration_model import Integration
from api.settings import settings


class IntegrationDAO:
    """Provides access to the integrations table with transparent Fernet encryption."""

    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session

    def _cipher(self) -> Fernet:
        """Return a Fernet cipher seeded from settings."""
        return Fernet(settings.encryption_key.encode())

    def _encrypt(self, credentials: dict[str, Any]) -> str:
        """JSON-serialize and Fernet-encrypt credentials.

        :param credentials: Plain-text credential dict.
        :return: Base64-encoded Fernet token.
        """
        return self._cipher().encrypt(json.dumps(credentials).encode()).decode()

    def _decrypt(self, token: str) -> dict[str, Any]:
        """Fernet-decrypt and JSON-parse credentials.

        :param token: Base64-encoded Fernet token.
        :return: Original credential dict.
        """
        raw: dict[str, Any] = json.loads(self._cipher().decrypt(token.encode()))
        return raw

    async def upsert(
        self,
        user_auth0_id: str,
        tool: str,
        credentials: dict[str, Any],
    ) -> Integration:
        """Insert or replace an integration for a user.

        :param user_auth0_id: Owner's Auth0 subject ID.
        :param tool: Integration identifier (e.g. "stripe").
        :param credentials: Plain-text credentials dict.
        :return: The persisted Integration.
        """
        encrypted = self._encrypt(credentials)
        stmt = (
            insert(Integration)
            .values(
                user_auth0_id=user_auth0_id,
                tool=tool,
                credentials_encrypted=encrypted,
            )
            .on_conflict_do_update(
                constraint="integrations_user_auth0_id_tool_key",
                set_={"credentials_encrypted": encrypted},
            )
            .returning(Integration)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_for_user(self, user_auth0_id: str) -> list[Integration]:
        """List all integrations for a user.

        :param user_auth0_id: Auth0 subject ID.
        :return: List of Integration rows (credentials still encrypted).
        """
        result = await self.session.execute(
            select(Integration).where(Integration.user_auth0_id == user_auth0_id)
        )
        return list(result.scalars().all())

    async def get_decrypted(self, user_auth0_id: str) -> dict[str, dict[str, Any]]:
        """Return decrypted credentials keyed by tool name.

        :param user_auth0_id: Auth0 subject ID.
        :return: Mapping of tool -> credentials dict.
        """
        integrations = await self.get_for_user(user_auth0_id)
        return {
            row.tool: self._decrypt(row.credentials_encrypted) for row in integrations
        }

    async def delete_tool(self, user_auth0_id: str, tool: str) -> None:
        """Remove an integration for a user.

        :param user_auth0_id: Auth0 subject ID.
        :param tool: Integration identifier to remove.
        """
        await self.session.execute(
            delete(Integration).where(
                Integration.user_auth0_id == user_auth0_id,
                Integration.tool == tool,
            )
        )
