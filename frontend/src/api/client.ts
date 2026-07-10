import type { ZodType } from "zod";

import {
  datasetListSchema,
  datasetRecordSchema,
  documentListSchema,
  documentRecordSchema,
  evaluationSummariesSchema,
  healthSchema,
  providerInfoSchema,
  presignedUploadSchema,
  readinessSchema,
  videoListSchema,
  videoRecordSchema,
  type EvaluationSummary,
  type Health,
  type KnowledgeSource,
  type ProviderInfo,
  type RetrievalReadiness,
} from "@/api/schemas";
import { pollReadiness, type ReadinessPollingOptions } from "@/api/readiness";

const REQUEST_TIMEOUT_MS = 10_000;

export class APIError extends Error {
  public constructor(message: string, public readonly status?: number) {
    super(message);
    this.name = "APIError";
  }
}

function endpoint(baseUrl: string, path: string): string {
  return `${baseUrl.replace(/\/$/, "")}${path}`;
}

async function request<T>(
  url: string,
  schema: ZodType<T>,
  init?: RequestInit,
  timeoutMs = REQUEST_TIMEOUT_MS,
): Promise<T> {
  const controller = new AbortController();
  const cancelFromCaller = () => controller.abort();
  if (init?.signal?.aborted) controller.abort();
  else init?.signal?.addEventListener("abort", cancelFromCaller, { once: true });
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...init, signal: controller.signal });
    if (!response.ok) {
      throw new APIError(
        response.status === 403
          ? "Direct uploads are unavailable in this environment."
          : `Synapse service returned status ${response.status}.`,
        response.status,
      );
    }
    const parsed = schema.safeParse(await response.json());
    if (!parsed.success) throw new APIError("Synapse returned an unexpected response.");
    return parsed.data;
  } catch (error) {
    if (error instanceof APIError) throw error;
    if (controller.signal.aborted) throw new APIError("The service is still waking up. Try again shortly.");
    throw new APIError("The service could not be reached.");
  } finally {
    window.clearTimeout(timeout);
    init?.signal?.removeEventListener("abort", cancelFromCaller);
  }
}

export async function getSystemReadiness(
  gatewayUrl: string,
  aiServiceUrl: string,
  options: ReadinessPollingOptions = {},
): Promise<{ gateway: Health; provider: ProviderInfo; retrieval: RetrievalReadiness }> {
  const requestInit = options.signal === undefined ? undefined : { signal: options.signal };
  const gateway = await request(endpoint(gatewayUrl, "/health"), healthSchema, requestInit);
  const retrieval = await pollReadiness(
    () => request(endpoint(aiServiceUrl, "/ready"), readinessSchema, requestInit, 20_000),
    options,
  );
  const provider = await request(
    endpoint(aiServiceUrl, "/api/v1/system/ai-provider"),
    providerInfoSchema,
    requestInit,
  );
  return { gateway, provider, retrieval };
}

export interface KnowledgeResult {
  sources: KnowledgeSource[];
  warnings: string[];
}

export async function listKnowledge(aiServiceUrl: string): Promise<KnowledgeResult> {
  const requests = await Promise.allSettled([
    request(endpoint(aiServiceUrl, "/api/v1/documents"), documentListSchema),
    request(endpoint(aiServiceUrl, "/api/v1/videos"), videoListSchema),
    request(endpoint(aiServiceUrl, "/api/v1/datasets"), datasetListSchema),
  ] as const);
  const [documents, videos, datasets] = requests;
  const warnings: string[] = [];
  if (documents.status === "rejected") warnings.push("PDF library unavailable");
  if (videos.status === "rejected") warnings.push("Video library unavailable");
  if (datasets.status === "rejected") warnings.push("Dataset library unavailable");

  return {
    sources: [
      ...(documents.status === "fulfilled"
        ? documents.value.documents.map((record) => ({ id: record.document_id, kind: "document" as const, record }))
        : []),
      ...(videos.status === "fulfilled"
        ? videos.value.videos.map((record) => ({ id: record.video_id, kind: "video" as const, record }))
        : []),
      ...(datasets.status === "fulfilled"
        ? datasets.value.datasets.map((record) => ({ id: record.dataset_id, kind: "dataset" as const, record }))
        : []),
    ],
    warnings,
  };
}

export async function getRecentEvaluationSummaries(
  aiServiceUrl: string,
  limit = 10,
): Promise<EvaluationSummary[]> {
  const result = await request(
    endpoint(aiServiceUrl, `/api/v1/evaluations/summaries?limit=${limit}`),
    evaluationSummariesSchema,
  );
  return result.summaries;
}

export type UploadKind = "document" | "video" | "dataset";

export async function uploadKnowledge(
  aiServiceUrl: string,
  gatewayUrl: string,
  kind: UploadKind,
  file: File,
  directUploadsEnabled: boolean,
): Promise<KnowledgeSource> {
  if (!directUploadsEnabled && kind !== "dataset") {
    const presigned = await request(endpoint(gatewayUrl, "/api/v1/uploads/presign"), presignedUploadSchema, {
      body: JSON.stringify({
        asset_type: kind,
        content_type: file.type,
        filename: file.name,
        size_bytes: file.size,
      }),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    });
    const signedUploadBody = new FormData();
    signedUploadBody.set("cacheControl", "3600");
    signedUploadBody.set("", file);
    const uploadResponse = await fetch(presigned.signed_upload_url, {
      body: signedUploadBody,
      headers: { "x-upsert": "false" },
      method: "PUT",
    });
    if (!uploadResponse.ok) throw new APIError("The browser-to-storage upload failed.", uploadResponse.status);
    const ingestionInit = {
      body: JSON.stringify({ object_path: presigned.object_path }),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    } satisfies RequestInit;
    if (kind === "document") {
      const record = await request(
        endpoint(gatewayUrl, "/api/v1/documents/from-storage"),
        documentRecordSchema,
        ingestionInit,
        120_000,
      );
      return { id: record.document_id, kind, record };
    }
    const record = await request(
      endpoint(gatewayUrl, "/api/v1/videos/from-storage"),
      videoRecordSchema,
      ingestionInit,
      120_000,
    );
    return { id: record.video_id, kind, record };
  }
  const body = new FormData();
  body.set("file", file);
  const init = { method: "POST", body } satisfies RequestInit;
  if (kind === "document") {
    const record = await request(endpoint(aiServiceUrl, "/api/v1/documents"), documentRecordSchema, init);
    return { id: record.document_id, kind, record };
  }
  if (kind === "video") {
    const record = await request(endpoint(aiServiceUrl, "/api/v1/videos"), videoRecordSchema, init);
    return { id: record.video_id, kind, record };
  }
  const record = await request(endpoint(aiServiceUrl, "/api/v1/datasets"), datasetRecordSchema, init);
  return { id: record.dataset_id, kind, record };
}
