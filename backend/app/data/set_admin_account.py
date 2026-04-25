import asyncio

from sqlalchemy import delete, select

from app.database import AsyncSessionLocal
from app.models.user import User
from app.utils.auth_utils import hash_password


NEW_ADMIN_EMAIL = "contact@kafundo.com"
NEW_ADMIN_PASSWORD = "Kafundo@2026!"
OLD_ADMIN_EMAIL = "admin@finveille.com"


async def main() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(User).where(User.email == OLD_ADMIN_EMAIL))

        result = await db.execute(select(User).where(User.email == NEW_ADMIN_EMAIL))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                email=NEW_ADMIN_EMAIL,
                password_hash=hash_password(NEW_ADMIN_PASSWORD),
                full_name="Administrateur Kafundo",
                role="admin",
                is_active=True,
            )
            db.add(user)
        else:
            user.password_hash = hash_password(NEW_ADMIN_PASSWORD)
            user.full_name = "Administrateur Kafundo"
            user.role = "admin"
            user.is_active = True

        await db.commit()
        print(f"Admin prêt : {NEW_ADMIN_EMAIL}")


if __name__ == "__main__":
    asyncio.run(main())
