class VideoError(Exception):
    code = "VIDEO_ERROR"
    status_code = 422


class VideoMediaTypeError(VideoError):
    code = "INVALID_VIDEO_MEDIA_TYPE"
    status_code = 415


class VideoTooLargeError(VideoError):
    code = "VIDEO_TOO_LARGE"
    status_code = 413


class VideoValidationError(VideoError):
    code = "INVALID_VIDEO"


class VideoDurationError(VideoError):
    code = "VIDEO_DURATION_EXCEEDED"
    status_code = 413


class VideoDependencyError(VideoError):
    code = "VIDEO_PROCESSOR_UNAVAILABLE"
    status_code = 503


class VideoProcessingError(VideoError):
    code = "VIDEO_PROCESSING_FAILED"


class VideoStorageError(VideoError):
    code = "VIDEO_STORAGE_ERROR"
    status_code = 500
