from pydantic import BaseModel, ConfigDict

from app.models.datasets import DatasetRecord


class DatasetListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    datasets: list[DatasetRecord]
