from collections import defaultdict
from decimal import Decimal
from typing import TypeAlias

from app.models.datasets import DatasetColumnType, StoredDataset
from app.schemas.analytics import (
    AggregateFunction,
    AggregationOperation,
    AnalyticsOperation,
    AnalyticsResult,
    AnalyticsValue,
    CountOperation,
    DescribeOperation,
    GroupByOperation,
    MaxOperation,
    MeanOperation,
    MinOperation,
    SortOperation,
    SumOperation,
    TopNOperation,
)
from app.services.analytics_errors import AnalyticsOperationError

TrustedRow: TypeAlias = dict[str, str | None]


class AnalyticsExecutor:
    """Closed deterministic executor: operation models map only to fixed application methods."""

    def __init__(self, *, max_result_rows: int) -> None:
        self._max_result_rows = max_result_rows

    def execute(
        self,
        dataset: StoredDataset,
        operation: AnalyticsOperation,
    ) -> AnalyticsResult:
        self._validate_operation(dataset, operation)
        if isinstance(operation, DescribeOperation):
            return self._describe(dataset, operation)
        if isinstance(operation, CountOperation):
            return self._count(dataset, operation)
        if isinstance(operation, (SumOperation, MeanOperation, MinOperation, MaxOperation)):
            return self._single_metric(dataset, operation)
        if isinstance(operation, GroupByOperation):
            return self._group_by(dataset, operation)
        if isinstance(operation, SortOperation):
            return self._sort(dataset, operation)
        if isinstance(operation, TopNOperation):
            return self._top_n(dataset, operation)
        if isinstance(operation, AggregationOperation):
            return self._aggregation(dataset, operation)
        raise AnalyticsOperationError("The analytics operation is not allowed.")

    def _validate_operation(self, dataset: StoredDataset, operation: AnalyticsOperation) -> None:
        columns = {item.name: item for item in dataset.dataset.columns}
        referenced: set[str] = set()
        numeric: set[str] = set()

        if isinstance(operation, DescribeOperation):
            referenced.update(operation.columns or columns)
        elif isinstance(operation, CountOperation):
            if operation.column is not None:
                referenced.add(operation.column)
        elif isinstance(operation, (SumOperation, MeanOperation, MinOperation, MaxOperation)):
            referenced.add(operation.column)
            numeric.add(operation.column)
        elif isinstance(operation, GroupByOperation):
            referenced.update(operation.grouping_fields)
            if operation.aggregation_field is not None:
                referenced.add(operation.aggregation_field)
                numeric.add(operation.aggregation_field)
            self._validate_limit(operation.limit)
        elif isinstance(operation, SortOperation):
            referenced.update(item.column for item in operation.sort_fields)
            self._validate_limit(operation.limit)
        elif isinstance(operation, TopNOperation):
            referenced.add(operation.column)
            numeric.add(operation.column)
            self._validate_limit(operation.n)
        elif isinstance(operation, AggregationOperation):
            referenced.update(operation.grouping_fields)
            for aggregate in operation.aggregations:
                if aggregate.field is not None:
                    referenced.add(aggregate.field)
                    if aggregate.function != "count":
                        numeric.add(aggregate.field)
            self._validate_limit(operation.limit)

        missing = sorted(referenced - columns.keys())
        if missing:
            raise AnalyticsOperationError(f"Unknown dataset columns: {', '.join(missing)}.")
        non_numeric = sorted(
            name for name in numeric if columns[name].data_type != DatasetColumnType.NUMBER
        )
        if non_numeric:
            raise AnalyticsOperationError(
                f"Numeric aggregation requires numeric columns: {', '.join(non_numeric)}."
            )

    def _validate_limit(self, value: int) -> None:
        if value > self._max_result_rows:
            raise AnalyticsOperationError(
                f"Result row limit cannot exceed {self._max_result_rows}."
            )

    def _describe(self, dataset: StoredDataset, operation: DescribeOperation) -> AnalyticsResult:
        selected = operation.columns or [item.name for item in dataset.dataset.columns]
        types = {item.name: item.data_type for item in dataset.dataset.columns}
        result_rows: list[dict[str, AnalyticsValue]] = []
        for column in selected:
            values = [row[column] for row in dataset.rows if row[column] is not None]
            row: dict[str, AnalyticsValue] = {
                "column": column,
                "type": types[column].value,
                "non_null_count": len(values),
                "unique_count": len(set(values)),
            }
            if types[column] == DatasetColumnType.NUMBER and values:
                numbers = [Decimal(value) for value in values if value is not None]
                row.update(
                    {
                        "min": self._public_number(min(numbers)),
                        "max": self._public_number(max(numbers)),
                        "mean": self._public_number(sum(numbers) / len(numbers)),
                    }
                )
            result_rows.append(row)
        return AnalyticsResult(
            summary=(
                f"Dataset {dataset.dataset.filename} contains {dataset.dataset.row_count} rows "
                f"and {len(dataset.dataset.columns)} columns."
            ),
            columns=list(result_rows[0].keys()) if result_rows else [],
            result_rows=result_rows,
            statistics={
                "row_count": dataset.dataset.row_count,
                "column_count": len(dataset.dataset.columns),
            },
            recommended_visualization="table",
        )

    def _count(self, dataset: StoredDataset, operation: CountOperation) -> AnalyticsResult:
        value = (
            len(dataset.rows)
            if operation.column is None
            else sum(row[operation.column] is not None for row in dataset.rows)
        )
        label = "rows" if operation.column is None else f"non-null {operation.column} values"
        return self._metric_result(f"Counted {value} {label}.", "count", value)

    def _single_metric(
        self,
        dataset: StoredDataset,
        operation: SumOperation | MeanOperation | MinOperation | MaxOperation,
    ) -> AnalyticsResult:
        function: AggregateFunction = operation.operation
        value = self._aggregate(dataset.rows, function, operation.column)
        public_value = self._public_number(value)
        return self._metric_result(
            f"{function} of {operation.column} is {public_value}.",
            function,
            public_value,
        )

    def _group_by(self, dataset: StoredDataset, operation: GroupByOperation) -> AnalyticsResult:
        grouped = self._group_rows(dataset.rows, operation.grouping_fields)
        rows: list[dict[str, AnalyticsValue]] = []
        value_name = (
            "count"
            if operation.aggregation == "count"
            else f"{operation.aggregation}_{operation.aggregation_field}"
        )
        for key, group_rows in sorted(grouped.items(), key=lambda item: item[0]):
            row: dict[str, AnalyticsValue] = dict(zip(operation.grouping_fields, key, strict=True))
            value = self._aggregate(
                group_rows,
                operation.aggregation,
                operation.aggregation_field,
            )
            row[value_name] = self._public_number(value)
            rows.append(row)
        rows = rows[: operation.limit]
        summary = self._rows_summary(
            f"Computed {operation.aggregation} grouped by {', '.join(operation.grouping_fields)}",
            rows,
        )
        return AnalyticsResult(
            summary=summary,
            columns=[*operation.grouping_fields, value_name],
            result_rows=rows,
            statistics={"group_count": len(grouped), "returned_rows": len(rows)},
            recommended_visualization="bar_chart",
        )

    def _sort(self, dataset: StoredDataset, operation: SortOperation) -> AnalyticsResult:
        rows = list(dataset.rows)
        types = {item.name: item.data_type for item in dataset.dataset.columns}
        for field in reversed(operation.sort_fields):
            present = [row for row in rows if row[field.column] is not None]
            missing = [row for row in rows if row[field.column] is None]
            present.sort(
                key=lambda row: self._sort_key(row[field.column], types[field.column]),
                reverse=field.direction == "desc",
            )
            rows = [*present, *missing]
        selected = rows[: operation.limit]
        public_rows = [self._public_row(dataset, row) for row in selected]
        return AnalyticsResult(
            summary=f"Sorted {len(public_rows)} rows using validated sort fields.",
            columns=[item.name for item in dataset.dataset.columns],
            result_rows=public_rows,
            statistics={"returned_rows": len(public_rows)},
            recommended_visualization="table",
        )

    def _top_n(self, dataset: StoredDataset, operation: TopNOperation) -> AnalyticsResult:
        column_type = next(
            item.data_type for item in dataset.dataset.columns if item.name == operation.column
        )
        present = [row for row in dataset.rows if row[operation.column] is not None]
        missing = [row for row in dataset.rows if row[operation.column] is None]
        rows = [
            *sorted(
                present,
                key=lambda row: self._sort_key(row[operation.column], column_type),
                reverse=True,
            ),
            *missing,
        ][: operation.n]
        public_rows = [self._public_row(dataset, row) for row in rows]
        return AnalyticsResult(
            summary=f"Selected the top {len(public_rows)} rows by {operation.column}.",
            columns=[item.name for item in dataset.dataset.columns],
            result_rows=public_rows,
            statistics={"returned_rows": len(public_rows)},
            recommended_visualization="table",
        )

    def _aggregation(
        self,
        dataset: StoredDataset,
        operation: AggregationOperation,
    ) -> AnalyticsResult:
        grouped = self._group_rows(dataset.rows, operation.grouping_fields)
        rows: list[dict[str, AnalyticsValue]] = []
        for key, group_rows in sorted(grouped.items(), key=lambda item: item[0]):
            row: dict[str, AnalyticsValue] = dict(zip(operation.grouping_fields, key, strict=True))
            for aggregate in operation.aggregations:
                value = self._aggregate(group_rows, aggregate.function, aggregate.field)
                row[aggregate.alias] = self._public_number(value)
            rows.append(row)
        rows = rows[: operation.limit]
        summary = self._rows_summary("Computed validated aggregation", rows)
        return AnalyticsResult(
            summary=summary,
            columns=[*operation.grouping_fields, *(item.alias for item in operation.aggregations)],
            result_rows=rows,
            statistics={"group_count": len(grouped), "returned_rows": len(rows)},
            recommended_visualization=("bar_chart" if operation.grouping_fields else "metric"),
        )

    @staticmethod
    def _group_rows(
        rows: list[TrustedRow],
        grouping_fields: list[str],
    ) -> dict[tuple[str, ...], list[TrustedRow]]:
        if not grouping_fields:
            return {(): rows}
        grouped: dict[tuple[str, ...], list[TrustedRow]] = defaultdict(list)
        for row in rows:
            key = tuple(row[field] or "" for field in grouping_fields)
            grouped[key].append(row)
        return dict(grouped)

    @staticmethod
    def _aggregate(
        rows: list[TrustedRow],
        function: AggregateFunction,
        field: str | None,
    ) -> Decimal:
        if function == "count":
            if field is None:
                return Decimal(len(rows))
            return Decimal(sum(row[field] is not None for row in rows))
        if field is None:
            raise AnalyticsOperationError("A numeric aggregation field is required.")
        values = [Decimal(value) for row in rows if (value := row[field]) is not None]
        if not values:
            raise AnalyticsOperationError(f"Column {field} has no numeric values.")
        if function == "sum":
            return sum(values, Decimal(0))
        if function == "mean":
            return sum(values, Decimal(0)) / len(values)
        if function == "min":
            return min(values)
        if function == "max":
            return max(values)
        raise AnalyticsOperationError("The aggregation function is not allowed.")

    @staticmethod
    def _public_number(value: Decimal | int | float) -> int | float:
        decimal = value if isinstance(value, Decimal) else Decimal(str(value))
        return int(decimal) if decimal == decimal.to_integral_value() else float(decimal)

    @classmethod
    def _public_row(cls, dataset: StoredDataset, row: TrustedRow) -> dict[str, AnalyticsValue]:
        types = {item.name: item.data_type for item in dataset.dataset.columns}
        public: dict[str, AnalyticsValue] = {}
        for column, value in row.items():
            if value is None:
                public[column] = None
            elif types[column] == DatasetColumnType.NUMBER:
                public[column] = cls._public_number(Decimal(value))
            elif types[column] == DatasetColumnType.BOOLEAN:
                public[column] = value.casefold() == "true"
            else:
                public[column] = value
        return public

    @staticmethod
    def _sort_key(value: str | None, column_type: DatasetColumnType) -> tuple[bool, object]:
        if value is None:
            return (True, "")
        if column_type == DatasetColumnType.NUMBER:
            return (False, Decimal(value))
        if column_type == DatasetColumnType.BOOLEAN:
            return (False, value.casefold() == "true")
        return (False, value.casefold())

    @staticmethod
    def _metric_result(summary: str, label: str, value: AnalyticsValue) -> AnalyticsResult:
        return AnalyticsResult(
            summary=summary,
            columns=[label],
            result_rows=[{label: value}],
            statistics={label: value},
            recommended_visualization="metric",
        )

    @staticmethod
    def _rows_summary(prefix: str, rows: list[dict[str, AnalyticsValue]]) -> str:
        rendered = "; ".join(
            ", ".join(f"{key}={value}" for key, value in row.items()) for row in rows
        )
        return f"{prefix}: {rendered}." if rendered else f"{prefix}: no rows."
