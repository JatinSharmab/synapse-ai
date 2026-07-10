import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { pollReadiness } from "../src/api/readiness.js";

describe("cold-start readiness polling", () => {
  it("retries with a bounded schedule and stops as soon as the service is ready", async () => {
    let attempts = 0;
    const waiting: number[] = [];
    const result = await pollReadiness(
      async () => {
        attempts += 1;
        if (attempts < 3) throw new Error("warming");
        return "ready";
      },
      { delaysMs: [0, 0, 0, 0], onWaiting: (attempt) => waiting.push(attempt) },
    );

    assert.equal(result, "ready");
    assert.equal(attempts, 3);
    assert.deepEqual(waiting, [1, 2]);
  });

  it("terminates after the configured number of attempts", async () => {
    let attempts = 0;
    await assert.rejects(
      pollReadiness(async () => {
        attempts += 1;
        throw new Error("still unavailable");
      }, { delaysMs: [0, 0, 0] }),
      /still unavailable/,
    );
    assert.equal(attempts, 3);
  });
});
