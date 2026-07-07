import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, it } from "node:test";

import { healthSchema, videoRecordSchema } from "../src/api/schemas.js";
import { seekVideo } from "../src/components/evidence/video-utils.js";
import { applyStreamEvent, initialStreamState } from "../src/workspace/stream-state.js";
import type { StreamEvent } from "../../shared/streaming.js";

const base = {
  schema_version: "1.0" as const,
  request_id: "request-1",
  correlation_id: "correlation-1",
};

describe("Phase 11 workspace state", () => {
  it("maps typed operational events to the required safe streaming states", () => {
    const events: StreamEvent[] = [
      { ...base, sequence: 1, type: "request.started", thread_id: "thread-1" },
      { ...base, sequence: 2, type: "route.selected", route: "document_search" },
      { ...base, sequence: 3, type: "retrieval.started", tool: "document_search" },
      { ...base, sequence: 4, type: "retrieval.completed", tool: "document_search", candidate_count: 2, latency_ms: 14 },
      { ...base, sequence: 5, type: "generation.started", route: "document_search" },
      { ...base, sequence: 6, type: "generation.token", token: "Grounded answer.", index: 0 },
      {
        ...base,
        sequence: 7,
        type: "guardrail.completed",
        result: {
          decision: "approve",
          groundedness_score: 0.95,
          citation_coverage: 1,
          prompt_injection_detected: false,
          schema_valid: true,
          reasons: ["GUARDRAILS_PASSED"],
          rewrite_required: false,
        },
        rewrite_count: 0,
      },
      { ...base, sequence: 8, type: "response.completed", final_response: "Grounded answer.", citations: [], citation_count: 0, latency_ms: 41, rewrite_count: 0 },
    ];
    const phases = events.map((event, index) => {
      const state = events.slice(0, index + 1).reduce(applyStreamEvent, initialStreamState());
      return state.phase;
    });
    assert.deepEqual(phases, ["Thinking", "Routing", "Searching Documents", "Searching Documents", "Synthesizing", "Synthesizing", "Validating", "Complete"]);

    const final = events.reduce(applyStreamEvent, initialStreamState());
    assert.equal(final.answer, "Grounded answer.");
    assert.equal(final.quality?.groundedness, 0.95);
    assert.equal(final.quality?.latencyMs, 41);
    assert.doesNotMatch(JSON.stringify(final.activity), /prompt|reasoning|draft_response|retrieved_context/i);
  });

  it("shows analytics and video as distinct operational states", () => {
    const analytics = applyStreamEvent(initialStreamState(), { ...base, sequence: 1, type: "route.selected", route: "data_analytics" });
    const video = applyStreamEvent(initialStreamState(), { ...base, sequence: 1, type: "retrieval.started", tool: "video_search" });
    assert.equal(analytics.phase, "Analyzing Data");
    assert.equal(video.phase, "Searching Video");
  });
});

describe("Phase 11 trust boundaries", () => {
  it("validates service readiness and rejects malformed source metadata", () => {
    assert.equal(healthSchema.safeParse({ service: "synapse-gateway", status: "ok", version: "0.10.0", environment: "development" }).success, true);
    assert.equal(videoRecordSchema.safeParse({ video_id: "forged" }).success, false);
  });

  it("jumps video evidence to the trusted start timestamp", () => {
    const media = { currentTime: 0 };
    seekVideo(media, 120.5);
    assert.equal(media.currentTime, 120.5);
    seekVideo(media, -1);
    assert.equal(media.currentTime, 120.5);
  });

  it("keeps Gen-UI fixed and uses Recharts without executable rendering paths", () => {
    const renderer = readFileSync(resolve(process.cwd(), "src/genui/renderer.tsx"), "utf8");
    assert.match(renderer, /from "recharts"/);
    assert.match(renderer, /Object\.freeze/);
    assert.doesNotMatch(renderer, /dangerouslySetInnerHTML|\beval\s*\(|\bFunction\s*\(|\bimport\s*\(/);
  });
});

describe("responsive workspace contracts", () => {
  it("defines mobile, tablet, and desktop layout adaptations", () => {
    const app = readFileSync(resolve(process.cwd(), "src/App.tsx"), "utf8");
    const workspace = readFileSync(resolve(process.cwd(), "src/components/chat/ai-workspace.tsx"), "utf8");
    assert.match(app, /lg:grid-cols-/);
    assert.match(app, /xl:grid-cols-/);
    assert.match(app, /lg:hidden/);
    assert.match(workspace, /md:grid-cols-2/);
    assert.match(workspace, /xl:grid-cols-/);
    assert.match(workspace, /xl:hidden/);
  });
});
