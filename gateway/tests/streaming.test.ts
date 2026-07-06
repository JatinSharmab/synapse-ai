import assert from "node:assert/strict";
import { describe, it } from "node:test";

import request from "supertest";

import { createApp, type GatewayRuntime } from "../src/app.js";

function runtime(fetchImplementation: typeof fetch, overrides: Partial<GatewayRuntime> = {}): GatewayRuntime {
  return {
    aiServiceUrl: "http://ai-service.test",
    corsOrigin: "http://localhost:5173",
    environment: "test",
    fetchImplementation,
    rateLimitMax: 30,
    rateLimitWindowMs: 60_000,
    upstreamTimeoutMs: 1_000,
    version: "0.10.0-test",
    ...overrides,
  };
}

describe("POST /api/v1/chat/stream", () => {
  it("validates, attaches IDs, forwards JSON, and proxies SSE unchanged", async () => {
    let forwardedUrl = "";
    let forwardedBody = "";
    let forwardedRequestId = "";
    let forwardedCorrelationId = "";
    const fetchImplementation: typeof fetch = async (input, init) => {
      forwardedUrl = String(input);
      forwardedBody = String(init?.body);
      const headers = new Headers(init?.headers);
      forwardedRequestId = headers.get("X-Request-ID") ?? "";
      forwardedCorrelationId = headers.get("X-Correlation-ID") ?? "";
      const data = JSON.stringify({
        correlation_id: forwardedCorrelationId,
        final_response: "RAG uses retrieved evidence.",
        request_id: forwardedRequestId,
        schema_version: "1.0",
        sequence: 1,
        type: "response.completed",
      });
      return new Response(`id: 1\nevent: response.completed\ndata: ${data}\n\n`, {
        headers: { "Content-Type": "text/event-stream" },
        status: 200,
      });
    };
    const app = createApp(runtime(fetchImplementation));

    const response = await request(app)
      .post("/api/v1/chat/stream")
      .set("Origin", "http://localhost:5173")
      .set("X-Correlation-ID", "correlation-browser")
      .send({ message: "Explain RAG", thread_id: "thread-stream" })
      .expect(200)
      .expect("Content-Type", /text\/event-stream/);

    assert.equal(forwardedUrl, "http://ai-service.test/api/v1/chat/stream");
    assert.deepEqual(JSON.parse(forwardedBody), {
      message: "Explain RAG",
      thread_id: "thread-stream",
    });
    assert.match(forwardedRequestId, /^[0-9a-f-]{36}$/);
    assert.equal(forwardedCorrelationId, "correlation-browser");
    assert.equal(response.headers["x-request-id"], forwardedRequestId);
    assert.equal(response.headers["x-correlation-id"], "correlation-browser");
    assert.equal(response.headers["access-control-expose-headers"], "X-Correlation-ID,X-Request-ID");
    assert.match(response.text, /event: response\.completed/);
    assert.doesNotMatch(response.text, /UPSTREAM_DISCONNECTED/);
  });

  it("rejects malformed requests before calling the AI service", async () => {
    let fetchCalls = 0;
    const fetchImplementation: typeof fetch = async () => {
      fetchCalls += 1;
      return new Response();
    };
    const app = createApp(runtime(fetchImplementation));

    const response = await request(app)
      .post("/api/v1/chat/stream")
      .send({ message: "", thread_id: "invalid thread", arbitrary: true })
      .expect(400);

    assert.equal(fetchCalls, 0);
    assert.equal(response.body.error.code, "INVALID_REQUEST");
    const requestId = response.headers["x-request-id"];
    assert.ok(requestId);
    assert.match(requestId, /^[0-9a-f-]{36}$/);
  });

  it("normalizes malformed JSON instead of returning an Express error page", async () => {
    const fetchImplementation: typeof fetch = async () => new Response();
    const app = createApp(runtime(fetchImplementation));

    const response = await request(app)
      .post("/api/v1/chat/stream")
      .set("Content-Type", "application/json")
      .send('{"message":')
      .expect(400)
      .expect("Content-Type", /json/);

    assert.equal(response.body.error.code, "INVALID_JSON");
    assert.doesNotMatch(response.text, /SyntaxError|node_modules|stack/i);
  });

  it("applies a lightweight per-client rate limit", async () => {
    const fetchImplementation: typeof fetch = async (_input, init) => {
      const headers = new Headers(init?.headers);
      const data = JSON.stringify({
        correlation_id: headers.get("X-Correlation-ID"),
        final_response: "Done.",
        request_id: headers.get("X-Request-ID"),
        schema_version: "1.0",
        sequence: 1,
        type: "response.completed",
      });
      return new Response(`id: 1\nevent: response.completed\ndata: ${data}\n\n`, {
        headers: { "Content-Type": "text/event-stream" },
      });
    };
    const app = createApp(runtime(fetchImplementation, { rateLimitMax: 1 }));
    const payload = { message: "Explain RAG", thread_id: "thread-rate" };

    await request(app).post("/api/v1/chat/stream").send(payload).expect(200);
    const response = await request(app).post("/api/v1/chat/stream").send(payload).expect(429);

    assert.equal(response.body.error.code, "RATE_LIMITED");
    assert.equal(response.headers["ratelimit-remaining"], "0");
    assert.ok(response.headers["retry-after"]);
  });

  it("converts an early upstream disconnect into a typed SSE error", async () => {
    const fetchImplementation: typeof fetch = async (_input, init) => {
      const headers = new Headers(init?.headers);
      const data = JSON.stringify({
        correlation_id: headers.get("X-Correlation-ID"),
        request_id: headers.get("X-Request-ID"),
        schema_version: "1.0",
        sequence: 1,
        thread_id: "thread-disconnect",
        type: "request.started",
      });
      return new Response(`id: 1\nevent: request.started\ndata: ${data}\n\n`, {
        headers: { "Content-Type": "text/event-stream" },
      });
    };
    const app = createApp(runtime(fetchImplementation));

    const response = await request(app)
      .post("/api/v1/chat/stream")
      .send({ message: "Explain RAG", thread_id: "thread-disconnect" })
      .expect(200);

    assert.match(response.text, /event: request\.started/);
    assert.match(response.text, /event: error/);
    assert.match(response.text, /UPSTREAM_DISCONNECTED/);
  });

  it("aborts the upstream request when the downstream client disconnects", async () => {
    let markUpstreamAborted: (() => void) | undefined;
    const upstreamAborted = new Promise<void>((resolve) => {
      markUpstreamAborted = resolve;
    });
    const fetchImplementation: typeof fetch = async (_input, init) => {
      const headers = new Headers(init?.headers);
      const data = JSON.stringify({
        correlation_id: headers.get("X-Correlation-ID"),
        request_id: headers.get("X-Request-ID"),
        schema_version: "1.0",
        sequence: 1,
        thread_id: "thread-client-close",
        type: "request.started",
      });
      const body = new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(new TextEncoder().encode(`id: 1\nevent: request.started\ndata: ${data}\n\n`));
          init?.signal?.addEventListener(
            "abort",
            () => {
              markUpstreamAborted?.();
              controller.close();
            },
            { once: true },
          );
        },
      });
      return new Response(body, { headers: { "Content-Type": "text/event-stream" } });
    };
    const app = createApp(runtime(fetchImplementation));
    const exchange = request(app)
      .post("/api/v1/chat/stream")
      .send({ message: "Explain RAG", thread_id: "thread-client-close" });
    const abortTimer = setTimeout(() => exchange.abort(), 250);

    await assert.rejects(exchange);
    clearTimeout(abortTimer);
    await Promise.race([
      upstreamAborted,
      new Promise<never>((_resolve, reject) =>
        setTimeout(() => reject(new Error("upstream was not aborted")), 500),
      ),
    ]);
  });

  it("normalizes an upstream timeout before streaming headers", async () => {
    const fetchImplementation: typeof fetch = async (_input, init) =>
      await new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(new Error("aborted")), { once: true });
      });
    const app = createApp(runtime(fetchImplementation, { upstreamTimeoutMs: 10 }));

    const response = await request(app)
      .post("/api/v1/chat/stream")
      .send({ message: "Explain RAG", thread_id: "thread-timeout" })
      .expect(504);

    assert.equal(response.body.error.code, "UPSTREAM_TIMEOUT");
    assert.equal(response.body.error.retryable, true);
  });

  it("does not expose a binary upload proxy route", async () => {
    let fetchCalls = 0;
    const fetchImplementation: typeof fetch = async () => {
      fetchCalls += 1;
      return new Response();
    };
    const app = createApp(runtime(fetchImplementation));

    await request(app)
      .post("/api/v1/documents")
      .set("Content-Type", "application/pdf")
      .send(Buffer.from("%PDF"))
      .expect(404);

    assert.equal(fetchCalls, 0);
  });
});
