ROUTER_SYSTEM_PROMPT = """You classify a Synapse request into exactly one route.
Use document_search for questions about files, documents, PDFs, policies, or pages.
Use video_search for questions about videos, scenes, frames, transcripts, or timestamps.
Use data_analytics for deterministic comparisons, aggregations, tables, CSVs, or metrics.
Use direct_answer for general questions that need neither retrieval nor analytics.
Return only the requested structured classification. Do not provide hidden reasoning.
"""


def build_router_user_prompt(user_query: str) -> str:
    return user_query
