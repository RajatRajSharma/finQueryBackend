"""Generate a small, TEXT-BASED annual-report PDF for end-to-end testing.

The real corpus in data/raw/ is image-only (scanned), so pypdf extracts zero
text and ingestion produces zero chunks. This script writes a synthetic but
realistic 10-K-style report with selectable text, so the full pipeline
(parse -> chunk -> embed -> store -> retrieve -> generate) can be exercised
live against Qdrant + Gemini.

    ./venv/Scripts/python.exe -m scripts.make_sample_pdf

Output: data/raw/Acme.pdf  (fictional company — safe, not real financial data).

Requires fpdf2 (dev-only; NOT a runtime dependency, so it's not in
requirements.txt). Install with: pip install fpdf2
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

# Fictional figures — clearly made up, used only to verify retrieval/citation.
PAGES: list[tuple[str, list[str]]] = [
    (
        "Acme Corporation - 2025 Annual Report",
        [
            "Acme Corporation is a fictional company used to test the FinQuery "
            "retrieval pipeline. Nothing here is real financial data.",
            "",
            "Business Overview",
            "Acme designs and sells industrial widgets and cloud-connected "
            "gadgets across North America, Europe, and Asia. The company "
            "operates two segments: Hardware and Services.",
        ],
    ),
    (
        "Financial Highlights",
        [
            "Total net sales for fiscal 2025 were $4,820 million, up 12 percent "
            "from $4,303 million in fiscal 2024.",
            "",
            "Operating income was $612 million, representing an operating margin "
            "of 12.7 percent. Net income was $471 million.",
            "",
            "The Hardware segment contributed $3,100 million of net sales, while "
            "the Services segment contributed $1,720 million.",
        ],
    ),
    (
        "Risk Factors",
        [
            "The company faces several risks, including the following:",
            "",
            "Supply chain concentration: a significant portion of widget "
            "components is sourced from a single region, exposing Acme to "
            "tariff and logistics disruption.",
            "",
            "Foreign exchange: roughly 40 percent of revenue is denominated in "
            "currencies other than the US dollar.",
            "",
            "Competition: larger competitors may undercut pricing on commodity "
            "gadgets, pressuring the Hardware segment's margins.",
        ],
    ),
]


def build(output: Path) -> None:
    pdf = FPDF()
    pdf.set_margins(left=20, top=20, right=20)
    pdf.set_auto_page_break(auto=True, margin=20)
    for title, paragraphs in PAGES:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.multi_cell(w=pdf.epw, h=10, text=title)
        pdf.ln(4)
        pdf.set_font("Helvetica", size=12)
        for para in paragraphs:
            if not para:
                pdf.ln(5)
            else:
                pdf.multi_cell(w=pdf.epw, h=7, text=para)
    output.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output))
    print(f"Wrote {output} ({output.stat().st_size} bytes, {len(PAGES)} pages)")


if __name__ == "__main__":
    build(Path("data/raw/Acme.pdf"))
