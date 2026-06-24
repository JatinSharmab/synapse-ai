"""Regenerate the deterministic Phase 4 document-retrieval fixture."""

from pathlib import Path

import pymupdf

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "sample-data" / "documents" / "synapse-policy.pdf"

PAGES = (
    (
        "Employee Benefits",
        (
            "The Orion commuter benefit provides a monthly transit allowance for eligible "
            "employees. "
            "Enrollment changes take effect on the first day of the following month."
        ),
    ),
    (
        "Refund Policy",
        (
            "Customers may request a refund within exactly 30 calendar days of purchase. "
            "The original "
            "receipt is required, and approved requests use the reference code ORION-30. Digital "
            "subscriptions become non-refundable after the first content download."
        ),
    ),
    (
        "Security Escalation",
        (
            "Critical security incidents must be reported to the response desk within fifteen "
            "minutes. "
            "The synthetic validation phrase for this page is blue heron protocol."
        ),
    ),
)


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open()
    document.set_metadata(
        {
            "title": "Synapse Phase 4 Policy Fixture",
            "author": "Synapse",
            "subject": "Deterministic page-aware retrieval fixture",
        }
    )
    for page_number, (heading, paragraph) in enumerate(PAGES, start=1):
        page = document.new_page(width=612, height=792)
        page.insert_text((72, 48), "Synapse Phase 4 Fixture", fontsize=9)
        page.insert_text((72, 100), heading, fontsize=18)
        page.insert_textbox(
            pymupdf.Rect(72, 135, 540, 300),
            paragraph,
            fontsize=11,
            lineheight=1.4,
        )
        page.insert_text((72, 744), f"Page {page_number}", fontsize=9)
    document.save(OUTPUT_PATH, garbage=4, deflate=True, no_new_id=True, reproducible=True)
    document.close()


if __name__ == "__main__":
    main()
