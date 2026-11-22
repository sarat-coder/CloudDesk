from __future__ import annotations

from app.models.entities import AuditLog
from app.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditLog]):
    model = AuditLog
