# Sample Data

`documents/synapse-policy.pdf` is a deterministic, non-sensitive three-page PDF used by Phase 4
tests and local demonstrations. Its page-specific facts make provenance checks reproducible:

- page 1 describes a commuter benefit;
- page 2 contains the 30-calendar-day refund policy and reference `ORION-30`;
- page 3 contains a blue-heron security escalation rule.

Regenerate the fixture from the repository root with:

```powershell
.\ai-service\.venv\Scripts\python.exe scripts\generate_sample_pdf.py
```

`evaluations/document-retrieval.v1.json` is the versioned Phase 5 retrieval dataset. It labels each
query with its relevant document filename, page, and global chunk index for deterministic Recall@K
and MRR comparisons between vector-only and hybrid retrieval.

`datasets/regional-revenue.csv` is the non-sensitive Phase 7 analytics fixture. It contains six
rows across three regions with numeric revenue/units and a boolean status column. Tests use its
known totals and grouped values to verify deterministic CSV typing, aggregation, sorting, top-N,
LangGraph planning, and numeric grounding.
