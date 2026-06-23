import re
from dataclasses import dataclass

from app.services.pdf_parser import ExtractedPage

TOKEN_PATTERN = re.compile(r"\w+(?:['’-]\w+)*|[^\w\s]", re.UNICODE)
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
NUMBERED_HEADING = re.compile(r"^(?:\d+(?:\.\d+)*|[A-Z])(?:[.)]|\s+-)\s+")


def estimate_tokens(text: str) -> int:
    return len(TOKEN_PATTERN.findall(text))


def _is_heading(text: str) -> bool:
    if len(text) > 120 or estimate_tokens(text) > 16 or text.endswith((".", "?", "!", ";")):
        return False
    letters = [character for character in text if character.isalpha()]
    return bool(letters) and (
        text.isupper()
        or text.istitle()
        or NUMBERED_HEADING.match(text) is not None
        or text.endswith(":")
    )


@dataclass(frozen=True)
class ChunkDraft:
    page_number: int
    text: str
    token_estimate: int


@dataclass(frozen=True)
class _SemanticUnit:
    text: str
    starts_section: bool = False


class SemanticChunker:
    def __init__(self, *, maximum_tokens: int, minimum_tokens: int, overlap_tokens: int) -> None:
        self._maximum_tokens = maximum_tokens
        self._minimum_tokens = minimum_tokens
        self._overlap_tokens = overlap_tokens

    def chunk_pages(self, pages: tuple[ExtractedPage, ...]) -> list[ChunkDraft]:
        drafts: list[ChunkDraft] = []
        for page in pages:
            for text in self._chunk_page(page.paragraphs):
                drafts.append(
                    ChunkDraft(
                        page_number=page.page_number,
                        text=text,
                        token_estimate=estimate_tokens(text),
                    )
                )
        return drafts

    def _chunk_page(self, paragraphs: tuple[str, ...]) -> list[str]:
        units: list[_SemanticUnit] = []
        for paragraph in paragraphs:
            units.extend(self._split_paragraph(paragraph))
        if not units:
            return []

        groups: list[list[str]] = []
        current: list[str] = []
        for unit in units:
            if unit.starts_section and current:
                groups.append(current)
                current = []
            prospective = "\n\n".join([*current, unit.text])
            if current and estimate_tokens(prospective) > self._maximum_tokens:
                groups.append(current)
                current = [unit.text]
            else:
                current.append(unit.text)
        if current:
            groups.append(current)

        groups = self._rebalance_small_tail(groups)
        groups = self._enforce_minimum(groups)
        base_chunks = ["\n\n".join(group) for group in groups]
        return self._apply_overlap(base_chunks)

    def _split_paragraph(self, paragraph: str) -> list[_SemanticUnit]:
        if estimate_tokens(paragraph) <= self._maximum_tokens:
            return [_SemanticUnit(paragraph, starts_section=_is_heading(paragraph))]

        sentences = [item.strip() for item in SENTENCE_BOUNDARY.split(paragraph) if item.strip()]
        units: list[_SemanticUnit] = []
        for sentence in sentences:
            if estimate_tokens(sentence) <= self._maximum_tokens:
                units.append(_SemanticUnit(sentence))
                continue
            tokens = TOKEN_PATTERN.findall(sentence)
            for start in range(0, len(tokens), self._maximum_tokens):
                units.append(_SemanticUnit(" ".join(tokens[start : start + self._maximum_tokens])))
        return units

    def _rebalance_small_tail(self, groups: list[list[str]]) -> list[list[str]]:
        if len(groups) < 2:
            return groups
        tail_tokens = estimate_tokens("\n\n".join(groups[-1]))
        if tail_tokens >= self._minimum_tokens:
            return groups

        combined = [*groups[-2], *groups[-1]]
        combined_text = "\n\n".join(combined)
        if estimate_tokens(combined_text) <= self._maximum_tokens:
            return [*groups[:-2], combined]

        for split_at in range(1, len(combined)):
            left = "\n\n".join(combined[:split_at])
            right = "\n\n".join(combined[split_at:])
            left_tokens = estimate_tokens(left)
            right_tokens = estimate_tokens(right)
            if (
                self._minimum_tokens <= left_tokens <= self._maximum_tokens
                and self._minimum_tokens <= right_tokens <= self._maximum_tokens
            ):
                return [*groups[:-2], combined[:split_at], combined[split_at:]]
        return groups

    def _enforce_minimum(self, groups: list[list[str]]) -> list[list[str]]:
        index = 0
        while index < len(groups) - 1:
            current_text = "\n\n".join(groups[index])
            if estimate_tokens(current_text) >= self._minimum_tokens:
                index += 1
                continue

            combined = [*groups[index], *groups[index + 1]]
            if estimate_tokens("\n\n".join(combined)) <= self._maximum_tokens:
                groups[index : index + 2] = [combined]
                continue

            next_group = groups[index + 1]
            while len(next_group) > 1:
                candidate = [*groups[index], next_group[0]]
                remaining = next_group[1:]
                if (
                    estimate_tokens("\n\n".join(candidate)) <= self._maximum_tokens
                    and estimate_tokens("\n\n".join(remaining)) >= self._minimum_tokens
                ):
                    groups[index] = candidate
                    groups[index + 1] = remaining
                    next_group = remaining
                    if estimate_tokens("\n\n".join(candidate)) >= self._minimum_tokens:
                        break
                else:
                    break

            if estimate_tokens("\n\n".join(groups[index])) < self._minimum_tokens:
                self._borrow_words_from_next(groups, index)
            index += 1
        return groups

    def _borrow_words_from_next(self, groups: list[list[str]], index: int) -> None:
        next_group = groups[index + 1]
        words = next_group[0].split()
        for take_count in range(1, len(words)):
            moved = " ".join(words[:take_count])
            remainder = " ".join(words[take_count:])
            candidate = [*groups[index], moved]
            remaining = [remainder, *next_group[1:]]
            if (
                estimate_tokens("\n\n".join(candidate)) >= self._minimum_tokens
                and estimate_tokens("\n\n".join(candidate)) <= self._maximum_tokens
                and estimate_tokens("\n\n".join(remaining)) >= self._minimum_tokens
            ):
                groups[index] = candidate
                groups[index + 1] = remaining
                return

    def _apply_overlap(self, chunks: list[str]) -> list[str]:
        if self._overlap_tokens == 0 or len(chunks) < 2:
            return chunks
        overlapped = [chunks[0]]
        for previous, current in zip(chunks, chunks[1:], strict=False):
            overlap = self._semantic_tail(previous)
            candidate = f"{overlap}\n\n{current}" if overlap else current
            overlapped.append(
                candidate if estimate_tokens(candidate) <= self._maximum_tokens else current
            )
        return overlapped

    def _semantic_tail(self, text: str) -> str:
        sentences = [item.strip() for item in SENTENCE_BOUNDARY.split(text) if item.strip()]
        selected: list[str] = []
        for sentence in reversed(sentences):
            prospective = " ".join([sentence, *selected])
            if estimate_tokens(prospective) > self._overlap_tokens:
                break
            selected.insert(0, sentence)
        if selected:
            return " ".join(selected)
        tokens = TOKEN_PATTERN.findall(text)
        return " ".join(tokens[-self._overlap_tokens :])
