import cors from "cors";
import express, { type Express, type NextFunction, type Request, type Response } from "express";
import helmet from "helmet";
import { randomUUID } from "node:crypto";

import type { Environment } from "./config.js";
import { FixedWindowRateLimiter } from "./rate-limit.js";
import { chatStreamRequestSchema } from "./schemas/chat.js";
import { healthResponseSchema } from "./schemas/health.js";
import { presignUploadRequestSchema, storedObjectRequestSchema } from "./schemas/uploads.js";
import { proxySSE, sendNormalizedError } from "./sse-proxy.js";
import { z } from "zod";

export interface GatewayRuntime {
  aiServiceUrl: string;
  corsOrigin: string;
  environment: Environment;
  fetchImplementation?: typeof fetch;
  rateLimitMax: number;
  rateLimitWindowMs: number;
  upstreamTimeoutMs: number;
  version: string;
}

const safeIdPattern = /^[A-Za-z0-9._:-]{1,128}$/;

interface RequestContext {
  correlationId: string;
  requestId: string;
}

function requestContext(response: Response): RequestContext {
  return response.locals.requestContext as RequestContext;
}

export function createApp(runtime: GatewayRuntime): Express {
  const app = express();
  const limiter = new FixedWindowRateLimiter(runtime.rateLimitMax, runtime.rateLimitWindowMs);

  app.disable("x-powered-by");
  app.use(helmet());
  app.use((request, response, next) => {
    const incomingCorrelationId = request.header("X-Correlation-ID");
    const context: RequestContext = {
      correlationId: incomingCorrelationId !== undefined && safeIdPattern.test(incomingCorrelationId)
        ? incomingCorrelationId
        : randomUUID(),
      requestId: randomUUID(),
    };
    response.locals.requestContext = context;
    response.set({ "X-Correlation-ID": context.correlationId, "X-Request-ID": context.requestId });
    if (runtime.environment !== "test") {
      const started = performance.now();
      response.once("finish", () => {
        console.info(JSON.stringify({
          correlation_id: context.correlationId,
          duration_ms: Number((performance.now() - started).toFixed(3)),
          event: "http.request.completed",
          method: request.method,
          path: request.path,
          request_id: context.requestId,
          service: "synapse-gateway",
          status: response.statusCode,
        }));
      });
    }
    next();
  });
  app.use(
    cors({
      exposedHeaders: ["X-Correlation-ID", "X-Request-ID"],
      origin: (origin, callback) => {
        callback(null, origin === undefined || origin === runtime.corsOrigin);
      },
    }),
  );
  app.use(express.json({ limit: "16kb", type: "application/json" }));

  app.use("/api/v1", (request, response, next) => {
    const context = requestContext(response);
    const rateLimit = limiter.consume(request.ip ?? "unknown");
    response.set({
      "RateLimit-Limit": String(rateLimit.limit),
      "RateLimit-Remaining": String(rateLimit.remaining),
      "RateLimit-Reset": String(Math.ceil(rateLimit.resetAt / 1_000)),
    });
    if (!rateLimit.allowed) {
      response.set("Retry-After", String(Math.max(1, Math.ceil((rateLimit.resetAt - Date.now()) / 1_000))));
      sendNormalizedError(response, 429, {
        code: "RATE_LIMITED",
        ...context,
        message: "Too many API requests. Retry after the rate-limit window.",
        retryable: true,
      });
      return;
    }
    next();
  });

  app.get("/health", (_request, response) => {
    const health = healthResponseSchema.parse({
      service: "synapse-gateway",
      status: "ok",
      version: runtime.version,
      environment: runtime.environment,
    });

    response.status(200).json(health);
  });

  const proxyJson = async (
    path: string,
    request: Request,
    response: Response,
    options: { body?: unknown; method: "GET" | "POST" },
  ): Promise<void> => {
    const { correlationId, requestId } = requestContext(response);
    const controller = new AbortController();
    let timedOut = false;
    const abortForClientDisconnect = () => {
      if (!response.writableEnded) controller.abort();
    };
    request.once("aborted", abortForClientDisconnect);
    response.once("close", abortForClientDisconnect);
    try {
      const timeout = setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, runtime.upstreamTimeoutMs);
      try {
        const upstream = await (runtime.fetchImplementation ?? fetch)(`${runtime.aiServiceUrl}${path}`, {
          ...(options.body === undefined ? {} : { body: JSON.stringify(options.body) }),
          headers: {
            ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
            "X-Correlation-ID": correlationId,
            "X-Request-ID": requestId,
          },
          method: options.method,
          signal: controller.signal,
        });
        if (!upstream.ok) {
          await upstream.body?.cancel();
          sendNormalizedError(response, upstream.status === 429 ? 429 : upstream.status >= 500 ? 502 : upstream.status, {
            code: "AI_SERVICE_ERROR",
            correlationId,
            message: "The AI service rejected the request.",
            requestId,
            retryable: upstream.status === 429 || upstream.status >= 500,
          });
          return;
        }
        if (!(upstream.headers.get("content-type") ?? "").toLowerCase().startsWith("application/json")) {
          await upstream.body?.cancel();
          sendNormalizedError(response, 502, {
            code: "INVALID_UPSTREAM_RESPONSE",
            correlationId,
            message: "The AI service returned an invalid response.",
            requestId,
            retryable: true,
          });
          return;
        }
        const payload: unknown = await upstream.json();
        response.status(upstream.status).json(payload);
      } finally {
        clearTimeout(timeout);
      }
    } catch {
      if (response.writableEnded || response.destroyed || request.aborted) return;
      sendNormalizedError(response, timedOut ? 504 : 502, {
        code: timedOut ? "UPSTREAM_TIMEOUT" : "UPSTREAM_UNAVAILABLE",
        correlationId,
        message: timedOut ? "The AI service exceeded the gateway timeout." : "The AI service is unavailable.",
        requestId,
        retryable: true,
      });
    } finally {
      request.off("aborted", abortForClientDisconnect);
      response.off("close", abortForClientDisconnect);
    }
  };

  const proxyGet = (publicPath: string, upstreamPath = publicPath): void => {
    app.get(publicPath, async (request, response) => {
      await proxyJson(upstreamPath, request, response, { method: "GET" });
    });
  };

  // This is an explicit control-plane allowlist. Binary upload routes are
  // intentionally absent so Vercel never becomes a PDF/video data path.
  proxyGet("/ready");
  proxyGet("/api/v1/system/ai-provider");
  proxyGet("/api/v1/documents");
  proxyGet("/api/v1/videos");
  proxyGet("/api/v1/datasets");
  app.get("/api/v1/evaluations/summaries", async (request, response) => {
    const parsed = z.coerce.number().int().min(1).max(100).safeParse(request.query.limit ?? 10);
    if (!parsed.success) {
      sendNormalizedError(response, 400, {
        code: "INVALID_REQUEST",
        ...requestContext(response),
        message: "The evaluation summary limit is invalid.",
        retryable: false,
      });
      return;
    }
    await proxyJson(
      `/api/v1/evaluations/summaries?limit=${encodeURIComponent(String(parsed.data))}`,
      request,
      response,
      { method: "GET" },
    );
  });

  app.post("/api/v1/uploads/presign", async (request, response) => {
    const parsed = presignUploadRequestSchema.safeParse(request.body);
    if (!parsed.success) {
      sendNormalizedError(response, 400, { code: "INVALID_REQUEST", ...requestContext(response), message: "The upload request is invalid.", retryable: false });
      return;
    }
    await proxyJson("/api/v1/uploads/presign", request, response, { body: parsed.data, method: "POST" });
  });

  app.post("/api/v1/documents/from-storage", async (request, response) => {
    const parsed = storedObjectRequestSchema.safeParse(request.body);
    if (!parsed.success) {
      sendNormalizedError(response, 400, { code: "INVALID_REQUEST", ...requestContext(response), message: "The stored object reference is invalid.", retryable: false });
      return;
    }
    await proxyJson("/api/v1/documents/from-storage", request, response, { body: parsed.data, method: "POST" });
  });

  app.post("/api/v1/videos/from-storage", async (request, response) => {
    const parsed = storedObjectRequestSchema.safeParse(request.body);
    if (!parsed.success) {
      sendNormalizedError(response, 400, { code: "INVALID_REQUEST", ...requestContext(response), message: "The stored object reference is invalid.", retryable: false });
      return;
    }
    await proxyJson("/api/v1/videos/from-storage", request, response, { body: parsed.data, method: "POST" });
  });

  app.post("/api/v1/chat/stream", async (request, response) => {
    const { correlationId, requestId } = requestContext(response);

    const parsed = chatStreamRequestSchema.safeParse(request.body);
    if (!parsed.success) {
      sendNormalizedError(response, 400, {
        code: "INVALID_REQUEST",
        correlationId,
        message: "The streaming request body is invalid.",
        requestId,
        retryable: false,
      });
      return;
    }

    await proxySSE({
      aiServiceUrl: runtime.aiServiceUrl,
      correlationId,
      fetchImplementation: runtime.fetchImplementation ?? fetch,
      payload: parsed.data,
      request,
      requestId,
      response,
      timeoutMs: runtime.upstreamTimeoutMs,
    });
  });

  app.use(
    (error: unknown, _request: Request, response: Response, _next: NextFunction) => {
      void _next;
      if (response.headersSent) {
        response.end();
        return;
      }
      const { correlationId, requestId } = requestContext(response);
      sendNormalizedError(response, 400, {
        code: error instanceof SyntaxError ? "INVALID_JSON" : "INVALID_REQUEST",
        correlationId,
        message: "The request could not be parsed.",
        requestId,
        retryable: false,
      });
    },
  );

  return app;
}
