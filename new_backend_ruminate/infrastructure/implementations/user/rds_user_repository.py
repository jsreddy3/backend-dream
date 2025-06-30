"""SQLAlchemy implementation of UserRepository using the primary DB (RDS)."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from new_backend_ruminate.domain.user.entities import User
from new_backend_ruminate.domain.user.repo import UserRepository

class RDSUserRepository(UserRepository):
    """Async SQLAlchemy implementation that keeps Google profile fresh."""

    async def upsert_google_user(self, claims: dict, session: AsyncSession) -> User:
        sub = claims["sub"]
        stmt = select(User).where(User.google_sub == sub)
        result = await session.execute(stmt)
        user: Optional[User] = result.scalars().first()

        if user:
            user.update_from_google_claims(claims)
            await session.commit()
            return user

        user = User(
            google_sub=sub,
            email=claims.get("email"),
            name=claims.get("name"),
            picture=claims.get("picture"),
        )
        session.add(user)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            # rare race – fetch existing instead
            return await self.get_by_sub(sub, session)
        return user

    async def get_by_id(self, uid: UUID, session: AsyncSession) -> Optional[User]:
        result = await session.execute(select(User).where(User.id == uid))
        return result.scalars().first()

    async def get_by_sub(self, sub: str, session: AsyncSession) -> Optional[User]:
        result = await session.execute(select(User).where(User.google_sub == sub))
        return result.scalars().first()
