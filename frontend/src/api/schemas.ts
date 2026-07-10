import { z } from "zod";

const dateString = z.string().datetime({ offset: true });

export const healthSchema = z
  .object({
    service: z.enum(["synapse-gateway", "synapse-ai-service"]),
    status: z.literal("ok"),
    version: z.string().min(1),
    environment: z.enum(["development", "test", "production"]),
  })
  .strict();

const indexReadinessSchema = z.object({
  state: z.enum(["starting", "rebuilding", "ready", "failed"]),
  durable_records: z.number().int().nonnegative(),
  indexed_records: z.number().int().nonnegative(),
  rebuilt: z.boolean(),
  error: z.string().nullable(),
}).strict();

export const readinessSchema = z.object({
  service: z.literal("synapse-ai-service"),
  status: z.enum(["ready", "not_ready"]),
  documents: indexReadinessSchema,
  videos: indexReadinessSchema,
  checked_at: dateString,
}).strict();

export const providerInfoSchema = z
  .object({
    provider: z.enum(["mock", "mistral"]),
    models: z
      .object({
        chat: z.string().min(1),
        vision: z.string().min(1),
        embedding: z.string().min(1),
      })
      .strict(),
    mock: z.boolean(),
  })
  .strict();

export const documentRecordSchema = z
  .object({
    document_id: z.string().min(1),
    filename: z.string().min(1),
    page_count: z.number().int().positive(),
    chunk_count: z.number().int().nonnegative(),
    checksum: z.string().length(64),
    created_at: dateString,
    ocr_required: z.boolean(),
  })
  .strict();

export const videoRecordSchema = z
  .object({
    video_id: z.string().min(1),
    filename: z.string().min(1),
    duration_seconds: z.number().positive(),
    size_bytes: z.number().int().positive(),
    width: z.number().int().positive(),
    height: z.number().int().positive(),
    has_audio: z.boolean(),
    segment_count: z.number().int().nonnegative(),
    processing_status: z.enum(["ready", "partial"]),
    visual_enrichment: z.enum(["completed", "disabled", "unavailable"]),
    transcription: z.enum(["completed", "disabled", "unavailable"]),
    created_at: dateString,
  })
  .strict();

const datasetColumnSchema = z
  .object({
    name: z.string().min(1),
    data_type: z.enum(["string", "number", "boolean"]),
    nullable: z.boolean(),
  })
  .strict();

export const datasetRecordSchema = z
  .object({
    dataset_id: z.string().min(1),
    filename: z.string().min(1),
    columns: z.array(datasetColumnSchema).min(1),
    row_count: z.number().int().positive(),
    checksum: z.string().length(64),
    created_at: dateString,
  })
  .strict();

export const documentListSchema = z.object({ documents: z.array(documentRecordSchema) }).strict();
export const videoListSchema = z.object({ videos: z.array(videoRecordSchema) }).strict();
export const datasetListSchema = z.object({ datasets: z.array(datasetRecordSchema) }).strict();

export const presignedUploadSchema = z.object({
  signed_upload_url: z.string().url(),
  object_path: z.string().min(3),
  expires_at: dateString,
}).strict();

const retrievalModeMetricsSchema = z.object({
  recall_at_k: z.number().min(0).max(1),
  mrr: z.number().min(0).max(1),
  average_latency_ms: z.number().nonnegative(),
}).strict();

export const evaluationSummarySchema = z.object({
  schema_version: z.literal("1.0"),
  run_id: z.string().regex(/^eval_[a-f0-9]{32}$/),
  timestamp: dateString,
  status: z.literal("completed"),
  configuration: z.object({
    dataset_id: z.string().min(1),
    dataset_version: z.string().min(1),
    dataset_checksum: z.string().regex(/^[a-f0-9]{64}$/),
    retrieval_k: z.number().int().positive(),
    retrieval_modes: z.array(z.enum(["vector_only", "hybrid"])),
    vector_top_k: z.number().int().positive(),
    bm25_top_k: z.number().int().positive(),
    rerank_top_k: z.number().int().positive(),
    final_context_k: z.number().int().positive(),
    deterministic: z.boolean(),
    random_seed: z.number().int(),
    fingerprint: z.string().regex(/^[a-f0-9]{64}$/),
  }).strict(),
  retrieval_mode: z.literal("vector_only_and_hybrid"),
  provider: z.enum(["mock", "mistral"]),
  model_identifier: z.string().min(1),
  retrieval: z.object({
    k: z.number().int().positive(),
    query_count: z.number().int().positive(),
    vector_only: retrievalModeMetricsSchema,
    hybrid: retrievalModeMetricsSchema,
  }).strict(),
  routing: z.object({
    case_count: z.number().int().positive(),
    route_accuracy: z.number().min(0).max(1),
    tool_selection_accuracy: z.number().min(0).max(1),
  }).strict(),
  generation: z.object({
    case_count: z.number().int().positive(),
    groundedness: z.number().min(0).max(1),
    citation_coverage: z.number().min(0).max(1),
    answer_relevance_proxy: z.number().min(0).max(1),
  }).strict(),
  guardrails: z.object({
    case_count: z.number().int().positive(),
    injection_detection_accuracy: z.number().min(0).max(1),
    unsupported_claim_detection_accuracy: z.number().min(0).max(1),
    block_rate: z.number().min(0).max(1),
    rewrite_rate: z.number().min(0).max(1),
  }).strict(),
  system: z.object({
    invocation_count: z.number().int().positive(),
    total_latency_ms: z.number().nonnegative(),
    retrieval_latency_ms: z.number().nonnegative(),
    generation_latency_ms: z.number().nonnegative(),
    guardrail_latency_ms: z.number().nonnegative(),
    provider_calls: z.number().int().nonnegative(),
    estimated_token_usage: z.number().int().nonnegative(),
  }).strict(),
}).strict();

export const evaluationSummariesSchema = z.object({
  summaries: z.array(evaluationSummarySchema),
}).strict();

export type Health = z.infer<typeof healthSchema>;
export type ProviderInfo = z.infer<typeof providerInfoSchema>;
export type RetrievalReadiness = z.infer<typeof readinessSchema>;
export type DocumentRecord = z.infer<typeof documentRecordSchema>;
export type VideoRecord = z.infer<typeof videoRecordSchema>;
export type DatasetRecord = z.infer<typeof datasetRecordSchema>;
export type EvaluationSummary = z.infer<typeof evaluationSummarySchema>;

export type KnowledgeSource =
  | { id: string; kind: "document"; record: DocumentRecord }
  | { id: string; kind: "video"; record: VideoRecord }
  | { id: string; kind: "dataset"; record: DatasetRecord };
