from app.services.pdf_parser import ExtractedPage
from app.services.semantic_chunker import SemanticChunker


def test_chunker_prefers_heading_paragraph_and_sentence_boundaries() -> None:
    page = ExtractedPage(
        page_number=7,
        paragraphs=(
            "REFUND CONDITIONS",
            (
                "First complete sentence preserves its boundary. Second complete sentence carries "
                "more detailed refund evidence. Third complete sentence finishes the paragraph."
            ),
            "SECURITY CONDITIONS",
            "A separate heading starts a separate semantic section with its own complete sentence.",
        ),
    )
    chunker = SemanticChunker(maximum_tokens=24, minimum_tokens=6, overlap_tokens=4)

    chunks = chunker.chunk_pages((page,))

    assert len(chunks) >= 2
    assert all(chunk.page_number == 7 for chunk in chunks)
    assert all(chunk.token_estimate >= 6 for chunk in chunks)
    assert all(chunk.token_estimate <= 24 for chunk in chunks)
    assert chunks[0].text.startswith("REFUND CONDITIONS")
    security_chunk = next(chunk for chunk in chunks if "SECURITY CONDITIONS" in chunk.text)
    assert security_chunk.text.index("SECURITY CONDITIONS") < security_chunk.text.index(
        "A separate heading"
    )
