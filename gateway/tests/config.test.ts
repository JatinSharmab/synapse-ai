import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { loadConfig } from "../src/config.js";

describe("production gateway configuration", () => {
  it("requires plain HTTPS service and CORS origins in production", () => {
    assert.throws(() => loadConfig({
      AI_SERVICE_URL: "http://ai.internal:8000/path",
      FRONTEND_ORIGIN: "*",
      NODE_ENV: "production",
    }));
    assert.deepEqual(loadConfig({
      AI_SERVICE_URL: "https://ai.example.test/",
      FRONTEND_ORIGIN: "https://synapse.example.test/",
      NODE_ENV: "production",
    }).aiServiceUrl, "https://ai.example.test");
  });

  it("accepts CORS_ORIGIN only as a backwards-compatible local alias", () => {
    const config = loadConfig({ CORS_ORIGIN: "http://localhost:5174", NODE_ENV: "development" });
    assert.equal(config.corsOrigin, "http://localhost:5174");
  });
});
