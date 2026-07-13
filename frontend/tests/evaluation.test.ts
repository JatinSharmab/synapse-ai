import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { evaluationSummarySchema } from "../src/api/schemas.js";

const summary = {
  schema_version: "1.0",
  run_id: "eval_0123456789abcdef0123456789abcdef",
  timestamp: "2026-07-10T00:00:00Z",
  status: "completed",
  configuration: {
    dataset_id: "synapse-internal-evaluation-v1",
    dataset_version: "1.0",
    dataset_checksum: "b".repeat(64),
    retrieval_k: 3,
    retrieval_modes: ["vector_only", "hybrid"],
    vector_top_k: 20,
    bm25_top_k: 20,
    rerank_top_k: 10,
    final_context_k: 5,
    deterministic: true,
    random_seed: 0,
    fingerprint: "a".repeat(64),
  },
  retrieval_mode: "vector_only_and_hybrid",
  provider: "mock",
  model_identifier: "mock-chat-v1",
  retrieval: {
    k: 3,
    query_count: 3,
    vector_only: { recall_at_k: 1, mrr: 1, average_latency_ms: 1 },
    hybrid: { recall_at_k: 1, mrr: 1, average_latency_ms: 2 },
  },
  routing: { case_count: 4, route_accuracy: 1, tool_selection_accuracy: 1 },
  generation: { case_count: 2, groundedness: 0.9, citation_coverage: 1, answer_relevance_proxy: 1 },
  guardrails: {
    case_count: 5,
    injection_detection_accuracy: 1,
    unsupported_claim_detection_accuracy: 1,
    block_rate: 0.4,
    rewrite_rate: 0.2,
  },
  system: {
    invocation_count: 6,
    total_latency_ms: 20,
    retrieval_latency_ms: 4,
    generation_latency_ms: 8,
    guardrail_latency_ms: 3,
    provider_calls: 12,
    estimated_token_usage: 300,
  },
};

describe("Phase 13 evaluation summary boundary", () => {
  it("accepts the strict aggregate metric envelope", () => {
    assert.equal(evaluationSummarySchema.safeParse(summary).success, true);
  });

  it("rejects hidden prompts or per-case answers added to the envelope", () => {
    assert.equal(evaluationSummarySchema.safeParse({ ...summary, system_prompt: "secret" }).success, false);
    assert.equal(evaluationSummarySchema.safeParse({ ...summary, final_response: "private case output" }).success, false);
  });
});
