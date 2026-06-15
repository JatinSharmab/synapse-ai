import assert from "node:assert/strict";
import { describe, it } from "node:test";

import request from "supertest";

import { createApp } from "../src/app.js";

describe("GET /health", () => {
  it("returns the typed gateway health contract", async () => {
    const app = createApp({
      corsOrigin: "http://localhost:5173",
      environment: "test",
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
  });
});

