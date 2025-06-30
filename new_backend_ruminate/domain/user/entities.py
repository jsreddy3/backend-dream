"""User domain entity (SQLAlchemy model)."""
from __future__ import annotations

from uuid import uuid4
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, DateTime, func

from new_backend_ruminate.infrastructure.db.meta import Base

class User(Base):
    """Persisted user identified by Google subject (sub)."""

    __tablename__ = "users"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    google_sub  = Column(String(64), unique=True, nullable=False)
    email       = Column(String(255), unique=True, nullable=False)
    name        = Column(String(255), nullable=True)
    picture     = Column(String(512), nullable=True)
    created     = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def update_from_google_claims(self, claims: dict[str, str | None]):
        """Update basic profile fields from Google claims in-place."""
        self.email = claims.get("email", self.email)
        self.name = claims.get("name", self.name)
        self.picture = claims.get("picture", self.picture)
