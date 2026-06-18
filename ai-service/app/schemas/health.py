from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.core.config import Environment


class HealthResponse(BaseModel):
    """Public process-liveness contract."""

    model_config = ConfigDict(extra="forbid")

    service: Literal["synapse-ai-service"] = "synapse-ai-service"
    status: Literal["ok"] = "ok"
    version: str
    environment: Environment
