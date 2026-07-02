import re
from math import isfinite
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

GenUIValue = str | int | float | bool | None
KEY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
UNSAFE_MARKUP_PATTERN = re.compile(
    r"<\s*/?\s*[a-z!][^>]*>|javascript\s*:|\bon[a-z]+\s*=",
    re.IGNORECASE,
)


def _validate_safe_value(value: object) -> None:
    if isinstance(value, str):
        if not value.strip():
            raise ValueError("Gen-UI strings must not be blank")
        if len(value) > 2_000:
            raise ValueError("Gen-UI strings must be at most 2,000 characters")
        if UNSAFE_MARKUP_PATTERN.search(value):
            raise ValueError("HTML, scripts, and event handlers are not allowed in Gen-UI")
    elif isinstance(value, dict):
        if len(value) > 20:
            raise ValueError("Gen-UI objects may contain at most 20 fields")
        for key, item in value.items():
            if not isinstance(key, str) or KEY_PATTERN.fullmatch(key) is None:
                raise ValueError("Gen-UI data keys must be safe identifiers")
            _validate_safe_value(item)
    elif isinstance(value, list):
        for item in value:
            _validate_safe_value(item)
    elif isinstance(value, float) and not isfinite(value):
        raise ValueError("Gen-UI numeric values must be finite")


class StrictGenUIModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )

    @model_validator(mode="after")
    def reject_unsafe_content(self) -> "StrictGenUIModel":
        _validate_safe_value(self.model_dump(mode="python"))
        return self


class ComponentBase(StrictGenUIModel):
    version: Literal["1.0"] = "1.0"
    title: str | None = Field(default=None, min_length=1, max_length=200)


class TextComponent(ComponentBase):
    type: Literal["text"] = "text"
    text: str = Field(min_length=1, max_length=2_000)


class MetricComponent(ComponentBase):
    type: Literal["metric"] = "metric"
    label: str = Field(min_length=1, max_length=120)
    value: str | int | float
    unit: str | None = Field(default=None, max_length=32)

    @field_validator("value")
    @classmethod
    def reject_boolean_metric(cls, value: str | int | float) -> str | int | float:
        if isinstance(value, bool):
            raise ValueError("Metric values cannot be boolean")
        return value


class XYChartConfig(StrictGenUIModel):
    xKey: str = Field(pattern=KEY_PATTERN.pattern)  # noqa: N815 - protocol uses camelCase
    yKey: str = Field(pattern=KEY_PATTERN.pattern)  # noqa: N815 - protocol uses camelCase


class PieChartConfig(StrictGenUIModel):
    labelKey: str = Field(pattern=KEY_PATTERN.pattern)  # noqa: N815
    valueKey: str = Field(pattern=KEY_PATTERN.pattern)  # noqa: N815


class BarChartComponent(ComponentBase):
    type: Literal["bar_chart"] = "bar_chart"
    title: str = Field(min_length=1, max_length=200)
    data: list[dict[str, GenUIValue]] = Field(min_length=1, max_length=100)
    config: XYChartConfig

    @model_validator(mode="after")
    def validate_chart_keys(self) -> "BarChartComponent":
        _validate_xy_rows(self.data, self.config.xKey, self.config.yKey)
        return self


class LineChartComponent(ComponentBase):
    type: Literal["line_chart"] = "line_chart"
    title: str = Field(min_length=1, max_length=200)
    data: list[dict[str, GenUIValue]] = Field(min_length=2, max_length=100)
    config: XYChartConfig

    @model_validator(mode="after")
    def validate_chart_keys(self) -> "LineChartComponent":
        _validate_xy_rows(self.data, self.config.xKey, self.config.yKey)
        return self


class PieChartComponent(ComponentBase):
    type: Literal["pie_chart"] = "pie_chart"
    title: str = Field(min_length=1, max_length=200)
    data: list[dict[str, GenUIValue]] = Field(min_length=1, max_length=30)
    config: PieChartConfig

    @model_validator(mode="after")
    def validate_chart_keys(self) -> "PieChartComponent":
        _validate_xy_rows(self.data, self.config.labelKey, self.config.valueKey)
        return self


class TableColumn(StrictGenUIModel):
    key: str = Field(pattern=KEY_PATTERN.pattern)
    label: str = Field(min_length=1, max_length=120)


class TableComponent(ComponentBase):
    type: Literal["table"] = "table"
    title: str = Field(min_length=1, max_length=200)
    columns: list[TableColumn] = Field(min_length=1, max_length=20)
    data: list[dict[str, GenUIValue]] = Field(max_length=100)

    @model_validator(mode="after")
    def validate_table_keys(self) -> "TableComponent":
        keys = [column.key for column in self.columns]
        if len(set(keys)) != len(keys):
            raise ValueError("Table column keys must be unique")
        for row in self.data:
            if any(key not in row for key in keys):
                raise ValueError("Every table row must contain every configured column key")
        return self


class CitationListItem(StrictGenUIModel):
    citation_id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=300)
    locator: str = Field(min_length=1, max_length=300)
    source_type: Literal["document", "video"]


class CitationListComponent(ComponentBase):
    type: Literal["citation_list"] = "citation_list"
    title: str = Field(default="Sources", min_length=1, max_length=200)
    citations: list[CitationListItem] = Field(min_length=1, max_length=20)


class VideoEvidenceItem(StrictGenUIModel):
    video_id: str = Field(min_length=1, max_length=128)
    filename: str = Field(min_length=1, max_length=255)
    segment_id: str = Field(min_length=1, max_length=128)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    description: str = Field(min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def validate_time_range(self) -> "VideoEvidenceItem":
        if self.end_seconds <= self.start_seconds:
            raise ValueError("Video evidence end_seconds must be greater than start_seconds")
        return self


class VideoEvidenceComponent(ComponentBase):
    type: Literal["video_evidence"] = "video_evidence"
    title: str = Field(default="Video evidence", min_length=1, max_length=200)
    items: list[VideoEvidenceItem] = Field(min_length=1, max_length=20)


GenUIComponent = Annotated[
    TextComponent
    | MetricComponent
    | BarChartComponent
    | LineChartComponent
    | PieChartComponent
    | TableComponent
    | CitationListComponent
    | VideoEvidenceComponent,
    Field(discriminator="type"),
]


class GenUIResponse(StrictGenUIModel):
    components: list[GenUIComponent] = Field(default_factory=list, max_length=5)


def _validate_xy_rows(
    rows: list[dict[str, GenUIValue]],
    label_key: str,
    numeric_key: str,
) -> None:
    if label_key == numeric_key:
        raise ValueError("Chart label and numeric keys must differ")
    for row in rows:
        if label_key not in row or numeric_key not in row:
            raise ValueError("Every chart row must contain the configured keys")
        numeric_value = row[numeric_key]
        if isinstance(numeric_value, bool) or not isinstance(numeric_value, (int, float)):
            raise ValueError("Chart numeric keys must reference finite numeric values")
