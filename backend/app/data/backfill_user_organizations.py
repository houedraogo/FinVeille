"""
Script de migration : créer une organisation personnelle pour chaque utilisateur
qui n'en possède pas encore.

Usage : docker exec kafundo-backend python -m app.data.backfill_user_organizations
"""
import asyncio
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.organization import Organization, OrganizationMember
from app.models.billing import Plan, Subscription


def _make_slug(base: str, suffix: str = "") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")[:40]
    return f"{slug}-{suffix}" if suffix else (slug or "org")


async def backfill(db: AsyncSession) -> None:
    # Charger le plan free
    free_plan = (await db.execute(select(Plan).where(Plan.slug == "free"))).scalar_one_or_none()

    # Tous les utilisateurs sans organisation
    users_result = await db.execute(select(User).where(User.is_active == True))
    users = list(users_result.scalars().all())

    created = 0
    skipped = 0

    for user in users:
        # Vérifier s'il est déjà membre d'une orga
        membership = (await db.execute(
            select(OrganizationMember.id).where(OrganizationMember.user_id == user.id)
        )).scalar_one_or_none()

        if membership:
            skipped += 1
            continue

        # Créer l'organisation personnelle
        base_name = (user.full_name or user.email.split("@")[0]).strip() or "org"
        base_slug = _make_slug(base_name)
        slug = base_slug
        counter = 1
        while True:
            existing = await db.execute(select(Organization.id).where(Organization.slug == slug))
            if not existing.scalar_one_or_none():
                break
            slug = _make_slug(base_slug, str(counter))
            counter += 1

        org = Organization(
            name=base_name,
            slug=slug,
            plan="free",
            status="active",
            created_by_id=user.id,
        )
        db.add(org)
        await db.flush()

        db.add(OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role="org_owner",
            is_active=True,
        ))

        if free_plan:
            db.add(Subscription(
                organization_id=org.id,
                plan_id=free_plan.id,
                status="active",
            ))

        user.default_organization_id = org.id
        await db.commit()

        print(f"  ✅  {user.email} → org '{org.name}' (slug: {slug})")
        created += 1

    print(f"\nRésultat : {created} organisations créées, {skipped} utilisateurs déjà rattachés.")


async def main() -> None:
    print("Backfill : création des organisations manquantes…\n")
    async with AsyncSessionLocal() as db:
        await backfill(db)


if __name__ == "__main__":
    asyncio.run(main())
