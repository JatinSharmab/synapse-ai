import unicodedata


def safe_upload_filename(filename: str, *, require_plain: bool = False) -> str:
    """Return a display-safe basename or reject unsafe/control-character input."""

    normalized = filename.replace("\\", "/")
    basename = normalized.rsplit("/", maxsplit=1)[-1].strip()
    if require_plain and basename != filename:
        raise ValueError("filename must not contain a path or surrounding whitespace")
    if (
        not basename
        or len(basename) > 255
        or basename in {".", ".."}
        or any(unicodedata.category(character) in {"Cc", "Cf"} for character in basename)
    ):
        raise ValueError("filename is invalid")
    return basename
