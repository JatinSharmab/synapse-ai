import { z } from "zod";

import { genUIComponentSchema } from "./genui.js";

const identifierSchema = z.string().min(1).max(128);
const routeSchema = z.enum([
  "document_search",
  "video_search",
  "data_analytics",
  "direct_answer",
]);
const eventBase = {
  schema_version: z.literal("1.0"),
  request_id: identifierSchema,
  correlation_id: identifierSchema,
  sequence: z.number().int().positive(),
};

const documentCitationSchema = z
  .object({
    citation_id: identifierSchema,
    source_type: z.literal("document"),
    document_id: identifierSchema,
    filename: z.string().min(1).max(255),
    page: z.number().int().positive(),
    chunk_id: identifierSchema,
    locator: z.string().min(1).max(300),
  })
  .strict();

const videoCitationSchema = z
  .object({
    citation_id: identifierSchema,
    source_type: z.literal("video"),
    video_id: identifierSchema,
    filename: z.string().min(1).max(255),
    segment_id: identifierSchema,
    start_seconds: z.number().finite().nonnegative(),
    end_seconds: z.number().finite().positive(),
    locator: z.string().min(1).max(300),
  })
  .strict();

const citationSchema = z.discriminatedUnion("source_type", [
  documentCitationSchema,
  videoCitationSchema,
]);

const guardrailResultSchema = z
  .object({
    decision: z.enum(["approve", "rewrite", "block"]),
    groundedness_score: z.number().finite().min(0).max(1),
    citation_coverage: z.number().finite().min(0).max(1),
    prompt_injection_detected: z.boolean(),
    schema_valid: z.boolean(),
    reasons: z.array(z.string().min(1).max(100)).min(1).max(20),
    rewrite_required: z.boolean(),
  })
  .strict();

const requestStartedSchema = z
  .object({
    ...eventBase,
    type: z.literal("request.started"),
    thread_id: identifierSchema,
  })
  .strict();

const routeSelectedSchema = z
  .object({ ...eventBase, type: z.literal("route.selected"), route: routeSchema })
  .strict();

const retrievalStartedSchema = z
  .object({
    ...eventBase,
    type: z.literal("retrieval.started"),
    tool: z.enum(["document_search", "video_search"]),
  })
  .strict();

const retrievalCompletedSchema = z
  .object({
    ...eventBase,
    type: z.literal("retrieval.completed"),
    tool: z.enum(["document_search", "video_search"]),
    candidate_count: z.number().int().min(0).max(100),
    latency_ms: z.number().int().nonnegative(),
  })
  .strict();

const generationStartedSchema = z
  .object({ ...eventBase, type: z.literal("generation.started"), route: routeSchema })
  .strict();

const generationTokenSchema = z
  .object({
    ...eventBase,
    type: z.literal("generation.token"),
    token: z.string().min(1).max(1_000),
    index: z.number().int().nonnegative(),
  })
  .strict();

const genUICreatedSchema = z
  .object({
    ...eventBase,
    type: z.literal("genui.created"),
    components: z.array(genUIComponentSchema).min(1).max(5),
  })
  .strict();

const guardrailCompletedSchema = z
  .object({
    ...eventBase,
    type: z.literal("guardrail.completed"),
    result: guardrailResultSchema,
    rewrite_count: z.number().int().min(0).max(1),
  })
  .strict();

const responseCompletedSchema = z
  .object({
    ...eventBase,
    type: z.literal("response.completed"),
    final_response: z.string().min(1).max(8_000),
    citations: z.array(citationSchema).max(20),
    citation_count: z.number().int().min(0).max(20),
    latency_ms: z.number().int().nonnegative(),
    rewrite_count: z.number().int().min(0).max(1),
  })
  .strict();

const errorSchema = z
  .object({
    ...eventBase,
    type: z.literal("error"),
    code: z.string().regex(/^[A-Z][A-Z0-9_]{1,63}$/),
    message: z.string().min(1).max(300),
    retryable: z.boolean(),
  })
  .strict();

export const streamEventSchema = z
  .discriminatedUnion("type", [
    requestStartedSchema,
    routeSelectedSchema,
    retrievalStartedSchema,
    retrievalCompletedSchema,
    generationStartedSchema,
    generationTokenSchema,
    genUICreatedSchema,
    guardrailCompletedSchema,
    responseCompletedSchema,
    errorSchema,
  ])
  .superRefine((event, context) => {
    if (event.type === "response.completed") {
      if (event.citation_count !== event.citations.length) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: "citation_count must match citations length",
        });
      }
      for (const citation of event.citations) {
        if (
          citation.source_type === "video" &&
          citation.end_seconds <= citation.start_seconds
        ) {
          context.addIssue({
            code: z.ZodIssueCode.custom,
            message: "Video citation end_seconds must be greater than start_seconds",
          });
        }
      }
    }
  });

export type StreamEvent = z.infer<typeof streamEventSchema>;
