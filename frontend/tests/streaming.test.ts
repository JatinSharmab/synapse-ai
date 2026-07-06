import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { parseSSEStream, StreamProtocolError, streamChat } from "../src/streaming/client.js";
import type { StreamEvent } from "../../shared/streaming.js";

function frame(event: Record<string, unknown>): string {
  return `id: ${String(event.sequence)}\nevent: ${String(event.type)}\ndata: ${JSON.stringify(event)}\n\n`;
}

describe("SSE client", () => {
  it("incrementally parses and validates typed events", async () => {
    const first = {
      schema_version: "1.0",
      request_id: "request-1",
      correlation_id: "correlation-1",
      sequence: 1,
      type: "request.started",
      thread_id: "thread-1",
    };
    const second = {
      schema_version: "1.0",
      request_id: "request-1",
      correlation_id: "correlation-1",
      sequence: 2,
      type: "generation.token",
      token: "Safe ",
      index: 0,
    };
    const encoded = new TextEncoder().encode(frame(first) + frame(second));
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoded.slice(0, 37));
        controller.enqueue(encoded.slice(37));
        controller.close();
      },
    });
    const events: StreamEvent[] = [];

    await parseSSEStream(new Response(body), (event) => events.push(event));

    assert.deepEqual(
      events.map((event) => event.type),
      ["request.started", "generation.token"],
    );
  });

  it("fails closed when envelope metadata and typed data disagree", async () => {
    const event = {
      schema_version: "1.0",
      request_id: "request-1",
      correlation_id: "correlation-1",
      sequence: 2,
      type: "generation.token",
      token: "Safe",
      index: 0,
    };
    const response = new Response(`id: 99\nevent: generation.token\ndata: ${JSON.stringify(event)}\n\n`);

    await assert.rejects(
      parseSSEStream(response, () => undefined),
      (error: unknown) => error instanceof StreamProtocolError,
    );
  });

  it("posts JSON to the gateway and consumes the proxied stream", async () => {
    let requestedUrl = "";
    let requestedBody = "";
    const event = {
      schema_version: "1.0",
      request_id: "request-1",
      correlation_id: "correlation-1",
      sequence: 1,
      type: "request.started",
      thread_id: "thread-1",
    };
    const fetchImplementation: typeof fetch = async (input, init) => {
      requestedUrl = String(input);
      requestedBody = String(init?.body);
      return new Response(frame(event), {
        headers: { "Content-Type": "text/event-stream" },
      });
    };
    const events: StreamEvent[] = [];

    await streamChat({
      fetchImplementation,
      gatewayUrl: "http://localhost:4000/",
      onEvent: (streamEvent) => events.push(streamEvent),
      request: { message: "Explain RAG", thread_id: "thread-1" },
    });

    assert.equal(requestedUrl, "http://localhost:4000/api/v1/chat/stream");
    assert.deepEqual(JSON.parse(requestedBody), {
      message: "Explain RAG",
      thread_id: "thread-1",
    });
    assert.equal(events.length, 1);
  });
});
