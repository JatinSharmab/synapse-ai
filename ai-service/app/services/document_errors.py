class DocumentError(Exception):
    code = "DOCUMENT_ERROR"
    status_code = 500


class DocumentMediaTypeError(DocumentError):
    code = "INVALID_PDF_MEDIA_TYPE"
    status_code = 415


class DocumentTooLargeError(DocumentError):
    code = "DOCUMENT_TOO_LARGE"
    status_code = 413


class DocumentValidationError(DocumentError):
    code = "INVALID_PDF"
    status_code = 422


class DocumentNotFoundError(DocumentError):
    code = "DOCUMENT_NOT_FOUND"
    status_code = 404


class DocumentStorageError(DocumentError):
    code = "DOCUMENT_STORAGE_ERROR"
    status_code = 500
