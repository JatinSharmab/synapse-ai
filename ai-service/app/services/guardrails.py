import re
from dataclasses import dataclass

from app.models.domain import (
    DocumentCitation,
    DocumentRetrievedContext,
    Route,
    ToolStatus,
    VideoCitation,
    VideoRetrievedContext,
)
from app.models.state import SynapseState
from app.prompts.guardrails import (
    SEMANTIC_GROUNDING_SYSTEM_PROMPT,
    build_semantic_grounding_prompt,
)
from app.providers.base import LLMProvider
from app.providers.errors import ProviderError
from app.schemas.genui import GenUIComponent, GenUIResponse
from app.schemas.guardrails import SemanticGroundingJudgement
from app.schemas.inference import InferenceMetadata

MAX_QUERY_LENGTH = 4_000
MIN_OUTPUT_LENGTH = 20
MAX_OUTPUT_LENGTH = 8_000
MIN_CONTEXT_SIMILARITY = 0.1
MIN_CLAIM_COVERAGE = 0.55
MAX_DETERMINISTIC_UNSUPPORTED_COVERAGE = 0.15

PROMPT_INJECTION_PATTERNS = (
    re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?\b", re.I),
    re.compile(r"\b(?:override|bypass|disable)\s+(?:the\s+)?(?:rules|policy|guardrails?)\b", re.I),
    re.compile(r"\b(?:act|behave)\s+as\s+(?:if\s+)?(?:there\s+are\s+)?no\s+rules\b", re.I),
)
SYSTEM_EXTRACTION_PATTERNS = (
    re.compile(r"\b(?:reveal|show|print|repeat|expose)\b.{0,40}\bsystem\s+prompt\b", re.I),
    re.compile(r"\b(?:developer|hidden)\s+(?:message|instructions?|prompt)\b", re.I),
    re.compile(r"\b(?:chain[- ]of[- ]thought|private\s+reasoning)\b", re.I),
)
DANGEROUS_TOOL_PATTERNS = (
    re.compile(
        r"\b(?:run|execute|invoke|open)\b.{0,40}"
        r"\b(?:shell|terminal|powershell|command\s+prompt|cmd\.exe)\b",
        re.I,
    ),
    re.compile(r"\b(?:eval|exec)\s*\(", re.I),
    re.compile(r"\b(?:delete|erase|wipe)\b.{0,40}\b(?:files?|database|disk|directory)\b", re.I),
)
UNSAFE_OUTPUT_PATTERN = re.compile(
    r"<\s*/?\s*[a-z!][^>]*>|javascript\s*:|\bon[a-z]+\s*=",
    re.I,
)
SECRET_PATTERNS = (
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\b(?:api[_ -]?key|secret|password)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{12,}", re.I),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}\b", re.I),
)
CITATION_REFERENCE_PATTERN = re.compile(r"\bcitation_[A-Za-z0-9_.:-]+\b", re.I)
PAGE_REFERENCE_PATTERN = re.compile(r"\bpage\s+(\d{1,6})\b", re.I)
TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", re.I)
NUMBER_PATTERN = re.compile(r"(?<!\w)-?\d+(?:\.\d+)?")
STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "document",
        "evidence",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "retrieved",
        "states",
        "that",
        "the",
        "this",
        "timestamped",
        "to",
        "video",
        "was",
        "with",
    }
)
NO_EVIDENCE_PHRASES = (
    "no indexed document evidence",
    "no indexed timestamped video evidence",
    "no evidence was found",
    "could not find relevant evidence",
)


@dataclass(frozen=True)
class InputGuardOutcome:
    passed: bool
    prompt_injection_detected: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class GroundingGuardOutcome:
    groundedness_score: float
    citation_coverage: float
    reasons: tuple[str, ...]
    rewrite_required: bool
    block_required: bool
    semantic_judgement_used: bool
    inference_metadata: tuple[InferenceMetadata, ...]


@dataclass(frozen=True)
class OutputGuardOutcome:
    genui: tuple[GenUIComponent, ...]
    schema_valid: bool
    reasons: tuple[str, ...]
    rewrite_required: bool
    block_required: bool


class InputGuard:
    """Deterministic checks applied before routing or provider inference."""

    def evaluate(self, query: str) -> InputGuardOutcome:
        reasons: list[str] = []
        if len(query) > MAX_QUERY_LENGTH:
            reasons.append("INPUT_QUERY_TOO_LONG")

        injection_detected = any(pattern.search(query) for pattern in PROMPT_INJECTION_PATTERNS)
        if injection_detected:
            reasons.append("INPUT_PROMPT_INJECTION")

        if any(pattern.search(query) for pattern in SYSTEM_EXTRACTION_PATTERNS):
            injection_detected = True
            reasons.append("INPUT_SYSTEM_PROMPT_EXTRACTION")

        if any(pattern.search(query) for pattern in DANGEROUS_TOOL_PATTERNS):
            reasons.append("INPUT_DANGEROUS_TOOL_INSTRUCTION")

        return InputGuardOutcome(
            passed=not reasons,
            prompt_injection_detected=injection_detected,
            reasons=tuple(reasons),
        )


class GroundingGuard:
    """Deterministically checks citations, provenance, relevance, and claim coverage."""

    def evaluate(
        self,
        state: SynapseState,
        provider: LLMProvider | None = None,
    ) -> GroundingGuardOutcome:
        contexts = state["retrieved_context"]
        citations = state["citations"]
        draft = (state["draft_response"] or "").strip()
        reasons: list[str] = []
        block_required = False
        rewrite_required = False
        semantic_judgement_used = False
        inference_metadata: tuple[InferenceMetadata, ...] = ()

        matched_context_ids: set[str] = set()
        for citation in citations:
            matched = next(
                (
                    context
                    for context in contexts
                    if self._citation_matches_context(citation, context)
                ),
                None,
            )
            if matched is None:
                reasons.append("GROUNDING_CITATION_NOT_IN_CONTEXT")
                block_required = True
            else:
                matched_context_ids.add(matched.context_id)

        denominator = max(len(contexts), len(citations), 1)
        citation_coverage = len(matched_context_ids) / denominator
        if contexts and citation_coverage < 1:
            reasons.append("GROUNDING_CITATION_COVERAGE_INCOMPLETE")
            block_required = True
        if citations and not contexts:
            reasons.append("GROUNDING_CITATION_WITHOUT_CONTEXT")
            block_required = True

        known_citation_ids = {citation.citation_id.casefold() for citation in citations}
        referenced_ids = {
            reference.casefold() for reference in CITATION_REFERENCE_PATTERN.findall(draft)
        }
        if referenced_ids - known_citation_ids:
            reasons.append("GROUNDING_UNKNOWN_CITATION_REFERENCE")
            block_required = True

        document_pages = {
            citation.page for citation in citations if isinstance(citation, DocumentCitation)
        }
        referenced_pages = {int(page) for page in PAGE_REFERENCE_PATTERN.findall(draft)}
        if referenced_pages and not referenced_pages.issubset(document_pages):
            reasons.append("GROUNDING_UNKNOWN_PAGE_REFERENCE")
            block_required = True

        if contexts:
            relevance = max(context.similarity_score for context in contexts)
            if relevance < MIN_CONTEXT_SIMILARITY:
                reasons.append("GROUNDING_CONTEXT_IRRELEVANT")
                rewrite_required = True

            claim_coverage = self._claim_coverage(state, draft)
            unsupported_number = self._has_unsupported_number(state, draft)
            if unsupported_number or claim_coverage <= MAX_DETERMINISTIC_UNSUPPORTED_COVERAGE:
                reasons.append("GROUNDING_UNSUPPORTED_CLAIM")
                rewrite_required = True
            elif claim_coverage < MIN_CLAIM_COVERAGE:
                if provider is None:
                    reasons.append("GROUNDING_SEMANTIC_REVIEW_REQUIRED")
                    rewrite_required = True
                else:
                    semantic_judgement_used = True
                    try:
                        judgement_result = provider.generate_structured(
                            system_prompt=SEMANTIC_GROUNDING_SYSTEM_PROMPT,
                            user_prompt=build_semantic_grounding_prompt(
                                user_query=state["user_query"],
                                draft_response=draft,
                                retrieved_context=contexts,
                                citations=citations,
                            ),
                            response_model=SemanticGroundingJudgement,
                        )
                    except ProviderError:
                        reasons.append("GROUNDING_SEMANTIC_JUDGE_UNAVAILABLE")
                        rewrite_required = True
                    else:
                        inference_metadata = (judgement_result.metadata,)
                        if (
                            not judgement_result.value.claim_supported
                            or not judgement_result.value.context_relevant
                        ):
                            reasons.append("GROUNDING_SEMANTIC_JUDGE_REJECTED")
                            rewrite_required = True
                        else:
                            claim_coverage = MIN_CLAIM_COVERAGE
            groundedness = round(
                min(1.0, (citation_coverage + claim_coverage + relevance) / 3),
                4,
            )
        elif state["route"] in {Route.DOCUMENT_SEARCH, Route.VIDEO_SEARCH}:
            citation_coverage = 1.0 if not citations else citation_coverage
            if any(phrase in draft.casefold() for phrase in NO_EVIDENCE_PHRASES):
                groundedness = 1.0
            else:
                groundedness = 0.0
                reasons.append("GROUNDING_UNSUPPORTED_CLAIM")
                rewrite_required = True
        elif state["route"] == Route.DATA_ANALYTICS:
            citation_coverage = 1.0 if not citations else citation_coverage
            selected_result = next(
                (
                    result
                    for result in reversed(state["tool_results"])
                    if result.tool == Route.DATA_ANALYTICS
                ),
                None,
            )
            if (
                selected_result is not None
                and selected_result.status == ToolStatus.COMPLETED
                and draft != selected_result.summary
            ):
                groundedness = 0.0
                reasons.append("GROUNDING_ANALYTICS_RESULT_MISMATCH")
                rewrite_required = True
            else:
                groundedness = 1.0
        else:
            citation_coverage = 1.0 if not citations else citation_coverage
            groundedness = 1.0

        return GroundingGuardOutcome(
            groundedness_score=groundedness,
            citation_coverage=round(citation_coverage, 4),
            reasons=_unique(reasons),
            rewrite_required=rewrite_required,
            block_required=block_required,
            semantic_judgement_used=semantic_judgement_used,
            inference_metadata=inference_metadata,
        )

    @staticmethod
    def _citation_matches_context(
        citation: DocumentCitation | VideoCitation,
        context: DocumentRetrievedContext | VideoRetrievedContext,
    ) -> bool:
        if isinstance(citation, DocumentCitation) and isinstance(context, DocumentRetrievedContext):
            return (
                citation.citation_id == f"citation_{context.chunk_id}"
                and citation.document_id == context.document_id
                and citation.filename == context.filename
                and citation.page == context.page
                and citation.chunk_id == context.chunk_id
                and citation.locator == f"{context.filename}, page {context.page}"
            )
        if isinstance(citation, VideoCitation) and isinstance(context, VideoRetrievedContext):
            return (
                citation.citation_id == f"citation_{context.segment_id}"
                and citation.video_id == context.video_id
                and citation.filename == context.filename
                and citation.segment_id == context.segment_id
                and citation.start_seconds == context.start_seconds
                and citation.end_seconds == context.end_seconds
                and citation.locator
                == (
                    f"{context.filename}, {context.start_seconds:.3f}s"
                    f"\N{EN DASH}{context.end_seconds:.3f}s"
                )
            )
        return False

    @staticmethod
    def _claim_coverage(state: SynapseState, draft: str) -> float:
        claim_tokens = _meaningful_tokens(draft)
        if not claim_tokens:
            return 1.0
        evidence_text = " ".join(
            [context.content for context in state["retrieved_context"]]
            + [citation.locator for citation in state["citations"]]
        )
        evidence_tokens = _meaningful_tokens(evidence_text)
        return len(claim_tokens & evidence_tokens) / len(claim_tokens)

    @staticmethod
    def _has_unsupported_number(state: SynapseState, draft: str) -> bool:
        answer_numbers = set(NUMBER_PATTERN.findall(draft))
        if not answer_numbers:
            return False
        supported_text = " ".join(
            [state["user_query"]]
            + [context.content for context in state["retrieved_context"]]
            + [citation.locator for citation in state["citations"]]
        )
        return not answer_numbers.issubset(set(NUMBER_PATTERN.findall(supported_text)))


class OutputGuard:
    """Validates the non-executable response envelope and detects sensitive output."""

    def evaluate(self, state: SynapseState) -> OutputGuardOutcome:
        draft = (state["draft_response"] or "").strip()
        reasons: list[str] = []
        rewrite_required = False
        block_required = False

        if len(draft) < MIN_OUTPUT_LENGTH:
            reasons.append("OUTPUT_TOO_SHORT")
            rewrite_required = True
        elif len(draft) > MAX_OUTPUT_LENGTH:
            reasons.append("OUTPUT_TOO_LONG")
            rewrite_required = True

        if UNSAFE_OUTPUT_PATTERN.search(draft):
            reasons.append("OUTPUT_SCRIPT_OR_HTML")
            block_required = True
        if any(pattern.search(draft) for pattern in SECRET_PATTERNS):
            reasons.append("OUTPUT_SECRET_PATTERN")
            block_required = True

        schema_valid = True
        try:
            validated_genui = GenUIResponse(components=state["genui"])
            genui = tuple(validated_genui.components)
        except ValueError:
            schema_valid = False
            genui = ()
            reasons.append("OUTPUT_GENUI_SCHEMA_INVALID")

        return OutputGuardOutcome(
            genui=genui,
            schema_valid=schema_valid,
            reasons=_unique(reasons),
            rewrite_required=rewrite_required,
            block_required=block_required,
        )


def _meaningful_tokens(text: str) -> set[str]:
    return {
        token
        for token in (match.casefold() for match in TOKEN_PATTERN.findall(text))
        if token not in STOP_WORDS and len(token) > 1
    }


def _unique(reasons: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(reasons))
