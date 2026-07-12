import assert from "node:assert/strict";
import { describe, it } from "node:test";

import request from "supertest";

import { createApp, type GatewayRuntime } from "../src/app.js";

function runtime(fetchImplementation: typeof fetch): GatewayRuntime {
  return {
    aiServiceUrl: "http://ai-service.test",
    corsOrigin: "http://localhost:5173",
    environment: "test",
    fetchImplementation,
    rateLimitMax: 30,
    rateLimitWindowMs: 60_000,
    upstreamTimeoutMs: 1_000,
    version: "0.12.0-test",
  };
}

describe("Phase 12 upload controls", () => {
  it("forwards only validated presign JSON", async () => {
    let forwardedBody = "";
    const app = createApp(runtime(async (_input, init) => {
      forwardedBody = String(init?.body);
      return new Response(JSON.stringify({
        expires_at: "2026-07-09T12:00:00Z",
        object_path: "documents/0123456789abcdef0123456789abcdef/policy.pdf",
        signed_upload_url: "https://storage.test/signed",
      }), { headers: { "Content-Type": "application/json" }, status: 200 });
    }));

    const response = await request(app).post("/api/v1/uploads/presign").send({
      asset_type: "document",
      content_type: "application/pdf",
      filename: "policy.pdf",
      size_bytes: 100,
    }).expect(200);

    assert.deepEqual(JSON.parse(forwardedBody), {
      asset_type: "document",
      content_type: "application/pdf",
      filename: "policy.pdf",
      size_bytes: 100,
    });
    assert.equal(response.body.object_path, "documents/0123456789abcdef0123456789abcdef/policy.pdf");
  });

  it("rejects binary/path-shaped presign input before upstream", async () => {
    let calls = 0;
    const app = createApp(runtime(async () => {
      calls += 1;
      return new Response();
    }));

    await request(app).post("/api/v1/uploads/presign").send({
      asset_type: "document",
      content_type: "application/pdf",
      filename: "../policy.pdf",
      size_bytes: 100,
    }).expect(400);

    assert.equal(calls, 0);
  });

  it("rejects MIME mismatches, control characters, and unsafe correlation IDs", async () => {
    let calls = 0;
    const app = createApp(runtime(async () => {
      calls += 1;
      return new Response();
    }));

    const mismatch = await request(app).post("/api/v1/uploads/presign")
      .set("X-Correlation-ID", "invalid value")
      .send({ asset_type: "document", content_type: "video/mp4", filename: "policy.pdf", size_bytes: 100 })
      .expect(400);
    await request(app).post("/api/v1/uploads/presign")
      .send({ asset_type: "document", content_type: "application/pdf", filename: "bad\u0000.pdf", size_bytes: 100 })
      .expect(400);
    await request(app).post("/api/v1/uploads/presign")
      .send({ asset_type: "document", content_type: "application/pdf", filename: "bidirectional\u202e.pdf", size_bytes: 100 })
      .expect(400);

    assert.equal(calls, 0);
    assert.match(String(mismatch.headers["x-correlation-id"]), /^[0-9a-f-]{36}$/);
    assert.equal(mismatch.body.error.code, "INVALID_REQUEST");
  });

  it("rate-limits upload controls as well as chat", async () => {
    const app = createApp({ ...runtime(async () => new Response(JSON.stringify({}), { headers: { "Content-Type": "application/json" } })), rateLimitMax: 1 });
    const payload = { asset_type: "document", content_type: "application/pdf", filename: "policy.pdf", size_bytes: 100 };

    await request(app).post("/api/v1/uploads/presign").send(payload).expect(200);
    const limited = await request(app).post("/api/v1/uploads/presign").send(payload).expect(429);

    assert.equal(limited.body.error.code, "RATE_LIMITED");
  });

  it("reports JSON proxy timeouts as 504 and hides upstream error bodies", async () => {
    const timeoutApp = createApp({
      ...runtime(async (_input, init) => await new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(new Error("aborted")), { once: true });
      })),
      upstreamTimeoutMs: 10,
    });
    const payload = { asset_type: "document", content_type: "application/pdf", filename: "policy.pdf", size_bytes: 100 };
    const timedOut = await request(timeoutApp).post("/api/v1/uploads/presign").send(payload).expect(504);

    const errorApp = createApp(runtime(async () => new Response(
      JSON.stringify({ detail: "mongodb://admin:secret@internal" }),
      { headers: { "Content-Type": "application/json" }, status: 500 },
    )));
    const upstreamError = await request(errorApp).post("/api/v1/uploads/presign").send(payload).expect(502);

    assert.equal(timedOut.body.error.code, "UPSTREAM_TIMEOUT");
    assert.equal(upstreamError.body.error.code, "AI_SERVICE_ERROR");
    assert.doesNotMatch(upstreamError.text, /admin|secret|mongodb/i);
  });
});
