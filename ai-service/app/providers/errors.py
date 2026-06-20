class ProviderError(Exception):
    """Base error that is safe to translate at the API boundary."""

    code = "AI_PROVIDER_ERROR"
    retryable = False


class ProviderConfigurationError(ProviderError):
    code = "AI_PROVIDER_CONFIGURATION_ERROR"


class ProviderRateLimitError(ProviderError):
    code = "AI_PROVIDER_RATE_LIMITED"


class ProviderTransientError(ProviderError):
    code = "AI_PROVIDER_UNAVAILABLE"
    retryable = True


class ProviderRequestError(ProviderError):
    code = "AI_PROVIDER_REQUEST_FAILED"


class ProviderResponseError(ProviderError):
    code = "AI_PROVIDER_INVALID_RESPONSE"
