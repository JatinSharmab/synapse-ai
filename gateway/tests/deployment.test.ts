import assert from "node:assert/strict";
import { describe, it } from "node:test";
import request from "supertest";

import { createApp, type GatewayRuntime } from "../src/app.js";

function runtime(fetchImplementation: typeof fetch): GatewayRuntime {
  return {
    aiServiceUrl: "https://ai.example.test",
    corsOrigin: "https://synapse.example.test",
    environment: "test",
    fetchImplementation,
    rateLimitMax: 100,
    rateLimitWindowMs: 60_000,
    upstreamTimeoutMs: 1_000,
    version: "0.15.0-test",
  };
}

describe("Vercel control-plane proxy", () => {
  it("forwards allowlisted JSON reads with request identifiers", async () => {
    const calls: Array<{ method: string; url: string; requestId: string | null }> = [];
    const fakeFetch: typeof fetch = async (input, init) => {
      const headers = new Headers(init?.headers);
      calls.push({
        method: init?.method ?? "GET",
        requestId: headers.get("X-Request-ID"),
        url: String(input),
      });
      return new Response(JSON.stringify({ status: "ready" }), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      });
    };
    const app = createApp(runtime(fakeFetch));

    for (const path of [
      "/ready",
      "/api/v1/system/ai-provider",
      "/api/v1/documents",
      "/api/v1/videos",
      "/api/v1/datasets",
      "/api/v1/evaluations/summaries?limit=7",
    ]) {
      const response = await request(app).get(path).set("Origin", "https://synapse.example.test");
      assert.equal(response.status, 200);
      assert.equal(response.headers["access-control-allow-origin"], "https://synapse.example.test");
    }

    assert.equal(calls.length, 6);
    assert.ok(calls.every((call) => call.method === "GET" && call.requestId !== null));
    assert.equal(calls.at(-1)?.url, "https://ai.example.test/api/v1/evaluations/summaries?limit=7");
  });

  it("rejects an invalid evaluation limit before contacting the AI service", async () => {
    let called = false;
    const fakeFetch: typeof fetch = async () => {
      called = true;
      return new Response("{}");
    };
    const response = await request(createApp(runtime(fakeFetch)))
      .get("/api/v1/evaluations/summaries?limit=1000");

    assert.equal(response.status, 400);
    assert.equal(called, false);
  });

  it("does not expose a generic binary upload proxy", async () => {
    const fakeFetch: typeof fetch = async () => new Response("{}");
    const response = await request(createApp(runtime(fakeFetch)))
      .post("/api/v1/uploads/raw")
      .set("Content-Type", "application/pdf")
      .send("%PDF");
    assert.equal(response.status, 404);
  });
});
