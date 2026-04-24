from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class JobResponse(BaseModel):
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None
