import assert from "node:assert/strict";
import { describe, it } from "node:test";

import request from "supertest";

import { createApp } from "../src/app.js";

describe("GET /health", () => {
  it("returns the typed gateway health contract", async () => {
    const app = createApp({
      aiServiceUrl: "http://127.0.0.1:8000",
      corsOrigin: "http://localhost:5173",
      environment: "test",
      rateLimitMax: 30,
      rateLimitWindowMs: 60_000,
      upstreamTimeoutMs: 130_000,
      version: "0.1.0-test",
    });

    const response = await request(app).get("/health").expect(200).expect("Content-Type", /json/);

    assert.deepEqual(response.body, {
      service: "synapse-gateway",
      status: "ok",
      version: "0.1.0-test",
      environment: "test",
    });
    assert.equal(response.headers["x-powered-by"], undefined);
    assert.equal(response.headers["x-content-type-options"], "nosniff");
    assert.match(String(response.headers["x-request-id"]), /^[0-9a-f-]{36}$/);
  });

  it("allows only the configured browser origin", async () => {
    const app = createApp({
      aiServiceUrl: "http://127.0.0.1:8000",
      corsOrigin: "https://synapse.example.test",
      environment: "test",
      rateLimitMax: 30,
      rateLimitWindowMs: 60_000,
      upstreamTimeoutMs: 1_000,
      version: "test",
    });

    const allowed = await request(app).get("/health").set("Origin", "https://synapse.example.test");
    const rejected = await request(app).get("/health").set("Origin", "https://attacker.example");

    assert.equal(allowed.headers["access-control-allow-origin"], "https://synapse.example.test");
    assert.equal(rejected.headers["access-control-allow-origin"], undefined);
  });
});
