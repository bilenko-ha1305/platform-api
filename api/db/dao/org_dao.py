"""Organisation DAO."""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.dependencies import get_db_session
from api.db.models.org_model import (
    Organization,
    OrganizationInvite,
    OrganizationMember,
)
from api.db.models.user_model import User


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "org"
    return f"{base}-{secrets.token_hex(4)}"


class OrgDAO:
    """Provides access to organisation, membership, and invite tables."""

    def __init__(self, session: AsyncSession = Depends(get_db_session)) -> None:
        self.session = session

    async def create(self, name: str, owner_auth0_id: str) -> Organization:
        """Create a new organisation and add the owner as admin.

        :param name: Display name of the organisation.
        :param owner_auth0_id: Auth0 ID of the founding user.
        :return: The new Organisation row.
        """
        org = Organization(
            name=name, slug=_slugify(name), owner_auth0_id=owner_auth0_id
        )
        self.session.add(org)
        await self.session.flush()
        member = OrganizationMember(
            org_id=org.id,
            user_auth0_id=owner_auth0_id,
            role="admin",
        )
        self.session.add(member)
        await self.session.flush()
        return org

    async def get_membership(self, user_auth0_id: str) -> OrganizationMember | None:
        """Return the membership row for a user (any org).

        :param user_auth0_id: Auth0 subject ID.
        :return: OrganizationMember or None.
        """
        result = await self.session.execute(
            select(OrganizationMember).where(
                OrganizationMember.user_auth0_id == user_auth0_id
            )
        )
        return result.scalar_one_or_none()

    async def get_for_user(self, user_auth0_id: str) -> Organization | None:
        """Return the organisation a user belongs to.

        :param user_auth0_id: Auth0 subject ID.
        :return: Organisation or None.
        """
        result = await self.session.execute(
            select(Organization)
            .join(
                OrganizationMember,
                OrganizationMember.org_id == Organization.id,
            )
            .where(OrganizationMember.user_auth0_id == user_auth0_id)
        )
        return result.scalar_one_or_none()

    async def get_by_stripe_customer_id(self, customer_id: str) -> Organization | None:
        """Fetch an organisation by Stripe customer ID.

        :param customer_id: Stripe cus_xxx identifier.
        :return: Organisation or None.
        """
        result = await self.session.execute(
            select(Organization).where(Organization.stripe_customer_id == customer_id)
        )
        return result.scalar_one_or_none()

    async def update_billing(
        self,
        org_id: uuid.UUID,
        stripe_customer_id: str,
        stripe_subscription_id: str | None,
        plan: str,
    ) -> None:
        """Persist Stripe billing info and update the plan.

        :param org_id: Organisation UUID.
        :param stripe_customer_id: Stripe cus_xxx identifier.
        :param stripe_subscription_id: Stripe sub_xxx identifier.
        :param plan: New plan name.
        """
        await self.session.execute(
            update(Organization)
            .where(Organization.id == org_id)
            .values(
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id,
                plan=plan,
            )
        )

    async def get_by_id(self, org_id: uuid.UUID) -> Organization | None:
        """Fetch an organisation by primary key.

        :param org_id: UUID primary key.
        :return: Organisation or None.
        """
        result = await self.session.execute(
            select(Organization).where(Organization.id == org_id)
        )
        return result.scalar_one_or_none()

    async def update_plan(self, org_id: uuid.UUID, plan: str) -> Organization:
        """Update the organisation's plan.

        :param org_id: Organisation UUID.
        :param plan: New plan identifier.
        :return: Updated Organisation row.
        """
        result = await self.session.execute(
            update(Organization)
            .where(Organization.id == org_id)
            .values(plan=plan)
            .returning(Organization)
        )
        return result.scalar_one()

    async def get_members_with_users(
        self, org_id: uuid.UUID
    ) -> list[tuple[OrganizationMember, User]]:
        """Return all members with their user profile, ordered by join date.

        :param org_id: Organisation UUID.
        :return: List of (member, user) tuples.
        """
        result = await self.session.execute(
            select(OrganizationMember, User)
            .join(User, User.auth0_id == OrganizationMember.user_auth0_id)
            .where(OrganizationMember.org_id == org_id)
            .order_by(OrganizationMember.joined_at)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def remove_member(self, org_id: uuid.UUID, user_auth0_id: str) -> None:
        """Remove a member from an organisation.

        :param org_id: Organisation UUID.
        :param user_auth0_id: Auth0 ID of member to remove.
        """
        await self.session.execute(
            delete(OrganizationMember).where(
                OrganizationMember.org_id == org_id,
                OrganizationMember.user_auth0_id == user_auth0_id,
            )
        )

    async def create_invite(
        self,
        org_id: uuid.UUID,
        email: str,
        role: str,
        invited_by: str,
    ) -> OrganizationInvite:
        """Create a 7-day invite token for an email address.

        :param org_id: Organisation UUID.
        :param email: Invitee e-mail address.
        :param role: Role to assign on acceptance.
        :param invited_by: Auth0 ID of the inviting admin.
        :return: The persisted OrganizationInvite row.
        """
        invite = OrganizationInvite(
            org_id=org_id,
            email=email,
            token=secrets.token_urlsafe(32),
            role=role,
            invited_by=invited_by,
            expires_at=datetime.now(tz=UTC) + timedelta(days=7),
        )
        self.session.add(invite)
        await self.session.flush()
        return invite

    async def get_invite_by_token(self, token: str) -> OrganizationInvite | None:
        """Fetch an invite by its URL token.

        :param token: URL-safe token string.
        :return: OrganizationInvite or None.
        """
        result = await self.session.execute(
            select(OrganizationInvite).where(OrganizationInvite.token == token)
        )
        return result.scalar_one_or_none()

    async def accept_invite(
        self, invite: OrganizationInvite, user_auth0_id: str
    ) -> OrganizationMember:
        """Accept an invite: create membership and mark invite used.

        :param invite: The OrganizationInvite to accept.
        :param user_auth0_id: Auth0 ID of the accepting user.
        :return: The new OrganizationMember row.
        """
        invite.accepted_at = datetime.now(tz=UTC)
        member = OrganizationMember(
            org_id=invite.org_id,
            user_auth0_id=user_auth0_id,
            role=invite.role,
            invited_by=invite.invited_by,
        )
        self.session.add(member)
        await self.session.flush()
        return member

    async def list_pending_invites(self, org_id: uuid.UUID) -> list[OrganizationInvite]:
        """Return unexpired, unaccepted invites for an organisation.

        :param org_id: Organisation UUID.
        :return: List of pending OrganizationInvite rows.
        """
        now = datetime.now(tz=UTC)
        result = await self.session.execute(
            select(OrganizationInvite).where(
                OrganizationInvite.org_id == org_id,
                OrganizationInvite.accepted_at.is_(None),
                OrganizationInvite.expires_at > now,
            )
        )
        return list(result.scalars().all())

    async def update_business_profile(
        self, org_id: uuid.UUID, profile: dict[str, Any]
    ) -> Organization:
        """Persist business profile data on the organisation.

        :param org_id: Organisation UUID.
        :param profile: Business profile dict.
        :return: Updated Organisation row.
        """
        result = await self.session.execute(
            update(Organization)
            .where(Organization.id == org_id)
            .values(business_profile=profile)
            .returning(Organization)
        )
        return result.scalar_one()

    async def delete_org(self, org_id: uuid.UUID) -> None:
        """Delete an organisation and all its associated data (CASCADE).

        :param org_id: Organisation UUID.
        """
        await self.session.execute(
            delete(Organization).where(Organization.id == org_id)
        )

    async def delete_invite(self, org_id: uuid.UUID, invite_id: uuid.UUID) -> None:
        """Delete (revoke) an invite.

        :param org_id: Organisation UUID (ownership check).
        :param invite_id: Invite primary key.
        """
        await self.session.execute(
            delete(OrganizationInvite).where(
                OrganizationInvite.id == invite_id,
                OrganizationInvite.org_id == org_id,
            )
        )
