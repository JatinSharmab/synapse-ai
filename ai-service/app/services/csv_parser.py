import csv
import io
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict

from app.models.datasets import DatasetColumn, DatasetColumnType
from app.services.analytics_errors import DatasetMediaTypeError, DatasetValidationError
from app.services.filenames import safe_upload_filename

CSV_MEDIA_TYPES = frozenset({"text/csv", "application/csv", "text/plain"})


class ParsedDataset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    filename: str
    columns: list[DatasetColumn]
    rows: list[dict[str, str | None]]


class CsvParser:
    def __init__(self, *, max_rows: int, max_columns: int) -> None:
        self._max_rows = max_rows
        self._max_columns = max_columns

    def parse(self, *, filename: str, content_type: str | None, data: bytes) -> ParsedDataset:
        try:
            safe_filename = safe_upload_filename(filename)
        except ValueError as error:
            raise DatasetValidationError("The CSV filename is invalid.") from error
        if not safe_filename.casefold().endswith(".csv"):
            raise DatasetMediaTypeError("The uploaded filename must use the .csv extension.")
        if content_type not in CSV_MEDIA_TYPES:
            raise DatasetMediaTypeError("Only CSV uploads are accepted.")
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise DatasetValidationError("The CSV must be UTF-8 encoded.") from error
        if "\x00" in text:
            raise DatasetValidationError("The CSV contains invalid null bytes.")

        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        try:
            raw_header = next(reader)
            header = [item.strip() for item in raw_header]
            self._validate_header(header)
            rows: list[dict[str, str | None]] = []
            for row_number, raw_row in enumerate(reader, start=2):
                if len(raw_row) != len(header):
                    raise DatasetValidationError(
                        f"CSV row {row_number} does not match the header width."
                    )
                if not any(value.strip() for value in raw_row):
                    continue
                rows.append(
                    {
                        column: value.strip() if value.strip() else None
                        for column, value in zip(header, raw_row, strict=True)
                    }
                )
                if len(rows) > self._max_rows:
                    raise DatasetValidationError("The CSV exceeds the configured row limit.")
        except (csv.Error, StopIteration) as error:
            raise DatasetValidationError("The CSV structure is invalid.") from error
        if not rows:
            raise DatasetValidationError("The CSV must contain at least one data row.")

        columns = [self._infer_column(name, rows) for name in header]
        return ParsedDataset(filename=safe_filename, columns=columns, rows=rows)

    def _validate_header(self, header: list[str]) -> None:
        if not header or any(not item for item in header):
            raise DatasetValidationError("CSV headers must be non-empty.")
        if len(header) > self._max_columns:
            raise DatasetValidationError("The CSV exceeds the configured column limit.")
        if len(set(header)) != len(header):
            raise DatasetValidationError("CSV headers must be unique.")
        if any(len(item) > 128 for item in header):
            raise DatasetValidationError("CSV headers must be at most 128 characters.")

    @staticmethod
    def _infer_column(name: str, rows: list[dict[str, str | None]]) -> DatasetColumn:
        values = [value for row in rows if (value := row[name]) is not None]
        nullable = len(values) != len(rows)
        if values and all(CsvParser._is_finite_decimal(value) for value in values):
            data_type = DatasetColumnType.NUMBER
        elif values and all(value.casefold() in {"true", "false"} for value in values):
            data_type = DatasetColumnType.BOOLEAN
        else:
            data_type = DatasetColumnType.STRING
        return DatasetColumn(name=name, data_type=data_type, nullable=nullable)

    @staticmethod
    def _is_finite_decimal(value: str) -> bool:
        try:
            return Decimal(value).is_finite()
        except InvalidOperation:
            return False
