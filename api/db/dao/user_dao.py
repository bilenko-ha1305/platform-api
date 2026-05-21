"""User DAO."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.dependencies import get_db_session
from api.db.models.user_model import User


class UserDAO:
    """Provides access to the users table."""

    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session

    async def upsert(
        self,
        auth0_id: str,
        email: str,
        name: str | None = None,
    ) -> User:
        """Insert or update a user by Auth0 ID.

        :param auth0_id: Auth0 subject ID (JWT sub claim).
        :param email: User email address.
        :param name: Display name from social login.
        :return: The persisted User instance.
        """
        stmt = (
            insert(User)
            .values(auth0_id=auth0_id, email=email, name=name)
            .on_conflict_do_update(
                index_elements=["auth0_id"],
                set_={"email": email, "name": name},
            )
            .returning(User)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_by_id(self, auth0_id: str) -> User | None:
        """Fetch a user by Auth0 ID.

        :param auth0_id: Auth0 subject ID.
        :return: User if found, else None.
        """
        result = await self.session.execute(
            select(User).where(User.auth0_id == auth0_id)
        )
        return result.scalar_one_or_none()
