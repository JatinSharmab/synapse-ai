import re
import unicodedata

TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[-_.][a-z0-9]+)*", re.IGNORECASE)
LEADING_REQUEST = re.compile(
    r"^(?:please\s+)?(?:find|locate|look\s+up|search\s+for|show\s+me|tell\s+me)\s+",
    re.IGNORECASE,
)
SOURCE_SUFFIX = re.compile(
    r"\s+(?:in|from)\s+(?:(?:my|the|uploaded)\s+)?(?:documents?|pdfs?|files?)\.?$",
    re.IGNORECASE,
)
STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "do",
        "does",
        "for",
        "how",
        "in",
        "is",
        "it",
        "of",
        "on",
        "please",
        "the",
        "this",
        "to",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
    }
)


def normalize_query(query: str) -> str:
    normalized = unicodedata.normalize("NFKC", query)
    normalized = " ".join(normalized.split()).strip()
    rewritten = SOURCE_SUFFIX.sub("", LEADING_REQUEST.sub("", normalized)).strip(" .?!")
    return (rewritten or normalized).casefold()


def tokenize(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return [token for token in TOKEN_PATTERN.findall(normalized) if token not in STOP_WORDS]


def normalized_phrase(text: str) -> str:
    return " ".join(TOKEN_PATTERN.findall(unicodedata.normalize("NFKC", text).casefold()))
