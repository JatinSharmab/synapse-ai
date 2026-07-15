import re
from collections import Counter
from dataclasses import dataclass

import pymupdf

from app.services.document_errors import (
    DocumentMediaTypeError,
    DocumentTooLargeError,
    DocumentValidationError,
)
from app.services.filenames import safe_upload_filename

PDF_MEDIA_TYPE = "application/pdf"
PDF_HEADER = b"%PDF-"


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    paragraphs: tuple[str, ...]

    @property
    def text(self) -> str:
        return "\n\n".join(self.paragraphs)


@dataclass(frozen=True)
class ParsedPdf:
    filename: str
    page_count: int
    pages: tuple[ExtractedPage, ...]
    extractable_character_count: int


class PdfParser:
    def __init__(self, *, max_upload_bytes: int, max_pages: int) -> None:
        self._max_upload_bytes = max_upload_bytes
        self._max_pages = max_pages

    def parse(self, *, filename: str, content_type: str | None, data: bytes) -> ParsedPdf:
        safe_filename = self._validate_filename(filename)
        if content_type != PDF_MEDIA_TYPE:
            raise DocumentMediaTypeError("Only application/pdf uploads are accepted.")
        if not data:
            raise DocumentValidationError("The uploaded PDF is empty.")
        if len(data) > self._max_upload_bytes:
            raise DocumentTooLargeError("The uploaded PDF exceeds the configured size limit.")
        if PDF_HEADER not in data[:1024]:
            raise DocumentMediaTypeError("The uploaded file does not contain a PDF signature.")

        try:
            with pymupdf.open(stream=data, filetype="pdf") as document:  # type: ignore[no-untyped-call]
                if not document.is_pdf:
                    raise DocumentValidationError("The uploaded file is not a valid PDF.")
                if document.needs_pass:
                    raise DocumentValidationError("Encrypted PDFs are not supported.")
                if document.page_count < 1:
                    raise DocumentValidationError("The PDF contains no pages.")
                if document.page_count > self._max_pages:
                    raise DocumentValidationError("The PDF exceeds the configured page limit.")
                raw_pages = [self._extract_blocks(page) for page in document]
                page_count = document.page_count
        except (pymupdf.EmptyFileError, pymupdf.FileDataError) as error:
            raise DocumentValidationError("The uploaded PDF is corrupt or unreadable.") from error

        cleaned_pages = self._remove_repeated_boilerplate(raw_pages)
        pages = tuple(
            ExtractedPage(page_number=index + 1, paragraphs=tuple(paragraphs))
            for index, paragraphs in enumerate(cleaned_pages)
        )
        character_count = sum(1 for page in pages for character in page.text if character.isalnum())
        return ParsedPdf(
            filename=safe_filename,
            page_count=page_count,
            pages=pages,
            extractable_character_count=character_count,
        )

    @staticmethod
    def _validate_filename(filename: str) -> str:
        try:
            safe_filename = safe_upload_filename(filename)
        except ValueError as error:
            raise DocumentValidationError("The PDF filename is invalid.") from error
        if not safe_filename.casefold().endswith(".pdf"):
            raise DocumentMediaTypeError("The uploaded filename must use the .pdf extension.")
        return safe_filename

    @classmethod
    def _extract_blocks(cls, page: pymupdf.Page) -> list[str]:
        paragraphs: list[str] = []
        for block in page.get_text("blocks", sort=True):  # type: ignore[no-untyped-call]
            if len(block) < 7 or block[6] != 0:
                continue
            cleaned = cls._normalize_block(str(block[4]))
            if cleaned:
                paragraphs.append(cleaned)
        return paragraphs

    @staticmethod
    def _normalize_block(text: str) -> str:
        text = text.replace("\u00ad", "").replace("\u00a0", " ").replace("\r", "\n")
        text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
        return re.sub(r"\s+", " ", " ".join(line for line in lines if line)).strip()

    @staticmethod
    def _remove_repeated_boilerplate(raw_pages: list[list[str]]) -> list[list[str]]:
        if len(raw_pages) < 2:
            return raw_pages
        edge_counts: Counter[str] = Counter()
        for paragraphs in raw_pages:
            if paragraphs:
                for candidate in {paragraphs[0], paragraphs[-1]}:
                    if len(candidate) <= 120:
                        edge_counts[candidate] += 1
        repeated = {text for text, count in edge_counts.items() if count >= 2}
        return [
            [paragraph for paragraph in paragraphs if paragraph not in repeated]
            for paragraphs in raw_pages
        ]
