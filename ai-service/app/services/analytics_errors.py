class AnalyticsError(Exception):
    code = "ANALYTICS_ERROR"
    status_code = 422


class DatasetMediaTypeError(AnalyticsError):
    code = "INVALID_CSV_MEDIA_TYPE"
    status_code = 415


class DatasetTooLargeError(AnalyticsError):
    code = "CSV_TOO_LARGE"
    status_code = 413


class DatasetValidationError(AnalyticsError):
    code = "INVALID_CSV"


class DatasetNotFoundError(AnalyticsError):
    code = "DATASET_NOT_FOUND"
    status_code = 404


class AnalyticsOperationError(AnalyticsError):
    code = "INVALID_ANALYTICS_OPERATION"


class AnalyticsStorageError(AnalyticsError):
    code = "ANALYTICS_STORAGE_ERROR"
    status_code = 500
