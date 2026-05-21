"""Organisation CRUD and invite endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.db.dao.org_dao import OrgDAO
from api.db.dao.user_dao import UserDAO
from api.db.models.org_model import Organization
from api.web.api.organizations.schema import (
    InviteCreateDTO,
    InviteDTO,
    MemberDTO,
    OrgCreateDTO,
    OrgDTO,
    OrgUpdatePlanDTO,
    PublicInviteDTO,
)
from api.web.dependencies.auth import verify_token
from api.web.dependencies.org import OrgContext, get_org_context

router = APIRouter()


async def _build_org_dto(org: Organization, org_dao: OrgDAO) -> OrgDTO:
    members_with_users = await org_dao.get_members_with_users(org.id)
    pending_invites = await org_dao.list_pending_invites(org.id)
    members = [
        MemberDTO(
            user_auth0_id=m.user_auth0_id,
            email=u.email,
            name=u.name,
            role=m.role,
            joined_at=m.joined_at,
        )
        for m, u in members_with_users
    ]
    return OrgDTO(
        id=org.id,
        name=org.name,
        slug=org.slug,
        plan=org.plan,
        has_billing=org.stripe_customer_id is not None,
        members=members,
        pending_invites=[InviteDTO.model_validate(i) for i in pending_invites],
    )


@router.post("/", response_model=OrgDTO, status_code=201)
async def create_org(
    body: OrgCreateDTO,
    user_payload: dict[str, Any] = Depends(verify_token),
    org_dao: OrgDAO = Depends(),
    user_dao: UserDAO = Depends(),
) -> OrgDTO:
    """Create a new organisation. The caller becomes the admin.

    :param body: Organisation name.
    :param user_payload: Decoded JWT claims.
    :param org_dao: Injected OrgDAO.
    :param user_dao: Injected UserDAO (ensures user row exists before FK insert).
    :raises HTTPException: 400 if user already belongs to an org.
    :return: Full OrgDTO with members and invites.
    """
    await user_dao.upsert(
        auth0_id=user_payload["sub"],
        email=user_payload.get("email", ""),
        name=user_payload.get("name"),
    )
    existing = await org_dao.get_membership(user_payload["sub"])
    if existing:
        raise HTTPException(
            status_code=400, detail="Already a member of an organisation"
        )
    org = await org_dao.create(name=body.name, owner_auth0_id=user_payload["sub"])
    return await _build_org_dto(org, org_dao)


@router.get("/me", response_model=OrgDTO)
async def get_my_org(
    ctx: OrgContext = Depends(get_org_context),
    org_dao: OrgDAO = Depends(),
) -> OrgDTO:
    """Return the current user's organisation.

    :param ctx: Resolved org context.
    :param org_dao: Injected OrgDAO.
    :return: Full OrgDTO.
    """
    org = await org_dao.get_by_id(ctx.org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organisation not found")
    return await _build_org_dto(org, org_dao)


@router.patch("/plan", response_model=OrgDTO)
async def update_plan(
    body: OrgUpdatePlanDTO,
    ctx: OrgContext = Depends(get_org_context),
    org_dao: OrgDAO = Depends(),
) -> OrgDTO:
    """Change the organisation's subscription plan (admin only).

    :param body: New plan identifier.
    :param ctx: Resolved org context.
    :param org_dao: Injected OrgDAO.
    :raises HTTPException: 403 if caller is not admin.
    :return: Updated OrgDTO.
    """
    if ctx.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    org = await org_dao.update_plan(ctx.org_id, body.plan)
    return await _build_org_dto(org, org_dao)


@router.post("/invites", response_model=InviteDTO, status_code=201)
async def create_invite(
    body: InviteCreateDTO,
    ctx: OrgContext = Depends(get_org_context),
    user_payload: dict[str, Any] = Depends(verify_token),
    org_dao: OrgDAO = Depends(),
) -> InviteDTO:
    """Generate an invite link for an e-mail address (admin only).

    :param body: Invitee email and role.
    :param ctx: Resolved org context.
    :param user_payload: Decoded JWT claims.
    :param org_dao: Injected OrgDAO.
    :raises HTTPException: 403 if caller is not admin.
    :return: InviteDTO with the invite token.
    """
    if ctx.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    invite = await org_dao.create_invite(
        org_id=ctx.org_id,
        email=str(body.email),
        role=body.role,
        invited_by=user_payload["sub"],
    )
    return InviteDTO.model_validate(invite)


@router.get("/invites/{token}", response_model=PublicInviteDTO)
async def get_invite_public(
    token: str,
    org_dao: OrgDAO = Depends(),
) -> PublicInviteDTO:
    """Return public invite metadata (no auth required).

    :param token: URL-safe invite token.
    :param org_dao: Injected OrgDAO.
    :raises HTTPException: 404 if token is unknown.
    :return: PublicInviteDTO with org name, email, expiry.
    """
    invite = await org_dao.get_invite_by_token(token)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    org = await org_dao.get_by_id(invite.org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organisation not found")
    now = datetime.now(tz=UTC)
    return PublicInviteDTO(
        org_name=org.name,
        email=invite.email,
        role=invite.role,
        expires_at=invite.expires_at,
        is_expired=invite.expires_at < now,
        is_accepted=invite.accepted_at is not None,
    )


@router.post("/invites/{token}/accept", response_model=MemberDTO, status_code=201)
async def accept_invite(
    token: str,
    user_payload: dict[str, Any] = Depends(verify_token),
    org_dao: OrgDAO = Depends(),
    user_dao: UserDAO = Depends(),
) -> MemberDTO:
    """Accept an invite and join the organisation.

    :param token: URL-safe invite token.
    :param user_payload: Decoded JWT claims.
    :param org_dao: Injected OrgDAO.
    :param user_dao: Injected UserDAO (for email lookup).
    :raises HTTPException: 400/404 on invalid/expired invite.
    :return: MemberDTO for the new membership.
    """
    await user_dao.upsert(
        auth0_id=user_payload["sub"],
        email=user_payload.get("email", ""),
        name=user_payload.get("name"),
    )
    invite = await org_dao.get_invite_by_token(token)
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if invite.accepted_at is not None:
        raise HTTPException(status_code=400, detail="Invite already accepted")
    now = datetime.now(tz=UTC)
    if invite.expires_at < now:
        raise HTTPException(status_code=400, detail="Invite has expired")

    existing = await org_dao.get_membership(user_payload["sub"])
    if existing:
        raise HTTPException(
            status_code=400, detail="Already a member of an organisation"
        )

    member = await org_dao.accept_invite(invite, user_payload["sub"])
    user = await user_dao.get_by_id(user_payload["sub"])
    return MemberDTO(
        user_auth0_id=member.user_auth0_id,
        email=user.email if user else user_payload.get("email", ""),
        name=user.name if user else user_payload.get("name"),
        role=member.role,
        joined_at=member.joined_at,
    )


@router.delete("/invites/{token}", status_code=204)
async def revoke_invite(
    token: str,
    ctx: OrgContext = Depends(get_org_context),
    org_dao: OrgDAO = Depends(),
) -> None:
    """Revoke a pending invite (admin only).

    :param token: URL-safe invite token.
    :param ctx: Resolved org context.
    :param org_dao: Injected OrgDAO.
    :raises HTTPException: 403 if not admin; 404 if invite not found.
    """
    if ctx.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    invite = await org_dao.get_invite_by_token(token)
    if not invite or invite.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="Invite not found")
    await org_dao.delete_invite(ctx.org_id, invite.id)


@router.delete("/members/{member_auth0_id}", status_code=204)
async def remove_member(
    member_auth0_id: str,
    ctx: OrgContext = Depends(get_org_context),
    user_payload: dict[str, Any] = Depends(verify_token),
    org_dao: OrgDAO = Depends(),
) -> None:
    """Remove a member from the organisation (admin only).

    :param member_auth0_id: Auth0 ID of the member to remove.
    :param ctx: Resolved org context.
    :param user_payload: Decoded JWT claims (prevents self-removal).
    :param org_dao: Injected OrgDAO.
    :raises HTTPException: 400 on self-removal; 403 if not admin.
    """
    if ctx.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    if member_auth0_id == user_payload["sub"]:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
    await org_dao.remove_member(ctx.org_id, member_auth0_id)
