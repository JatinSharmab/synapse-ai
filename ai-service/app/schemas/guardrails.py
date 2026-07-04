from typing import Literal

from pydantic import BaseModel, ConfigDict


class SemanticGroundingJudgement(BaseModel):
    """Bounded semantic signal; no rationale or private reasoning is requested."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_supported: bool
    context_relevant: bool
    reason_code: Literal["supported", "unsupported", "irrelevant"]
