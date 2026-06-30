from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AnalyticsValue = str | int | float | bool | None
AggregateFunction = Literal["count", "sum", "mean", "min", "max"]


class StrictAnalyticsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DescribeOperation(StrictAnalyticsModel):
    operation: Literal["describe"] = "describe"
    columns: list[str] | None = Field(default=None, max_length=50)


class CountOperation(StrictAnalyticsModel):
    operation: Literal["count"] = "count"
    column: str | None = None


class SumOperation(StrictAnalyticsModel):
    operation: Literal["sum"] = "sum"
    column: str


class MeanOperation(StrictAnalyticsModel):
    operation: Literal["mean"] = "mean"
    column: str


class MinOperation(StrictAnalyticsModel):
    operation: Literal["min"] = "min"
    column: str


class MaxOperation(StrictAnalyticsModel):
    operation: Literal["max"] = "max"
    column: str


class GroupByOperation(StrictAnalyticsModel):
    operation: Literal["group_by"] = "group_by"
    grouping_fields: list[str] = Field(min_length=1, max_length=3)
    aggregation: AggregateFunction
    aggregation_field: str | None = None
    limit: int = Field(default=100, ge=1, le=1_000)

    @model_validator(mode="after")
    def validate_aggregation_field(self) -> "GroupByOperation":
        if self.aggregation != "count" and self.aggregation_field is None:
            raise ValueError("aggregation_field is required for numeric group aggregation")
        return self


class SortField(StrictAnalyticsModel):
    column: str
    direction: Literal["asc", "desc"] = "asc"


class SortOperation(StrictAnalyticsModel):
    operation: Literal["sort"] = "sort"
    sort_fields: list[SortField] = Field(min_length=1, max_length=3)
    limit: int = Field(default=100, ge=1, le=1_000)


class TopNOperation(StrictAnalyticsModel):
    operation: Literal["top_n"] = "top_n"
    column: str
    n: int = Field(default=10, ge=1, le=1_000)


class AggregationSpec(StrictAnalyticsModel):
    function: AggregateFunction
    field: str | None = None
    alias: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z][A-Za-z0-9_]*$")

    @model_validator(mode="after")
    def validate_field(self) -> "AggregationSpec":
        if self.function != "count" and self.field is None:
            raise ValueError("field is required for numeric aggregation")
        return self


class AggregationOperation(StrictAnalyticsModel):
    operation: Literal["aggregation"] = "aggregation"
    aggregations: list[AggregationSpec] = Field(min_length=1, max_length=10)
    grouping_fields: list[str] = Field(default_factory=list, max_length=3)
    limit: int = Field(default=100, ge=1, le=1_000)


AnalyticsOperation = Annotated[
    DescribeOperation
    | CountOperation
    | SumOperation
    | MeanOperation
    | MinOperation
    | MaxOperation
    | GroupByOperation
    | SortOperation
    | TopNOperation
    | AggregationOperation,
    Field(discriminator="operation"),
]


class AnalyticsPlan(StrictAnalyticsModel):
    dataset_id: str
    operation: AnalyticsOperation


class AnalyticsExecuteRequest(StrictAnalyticsModel):
    dataset_id: str
    operation: AnalyticsOperation


class AnalyticsResult(StrictAnalyticsModel):
    summary: str
    columns: list[str]
    result_rows: list[dict[str, AnalyticsValue]]
    statistics: dict[str, AnalyticsValue]
    recommended_visualization: Literal["metric", "table", "bar_chart"]
