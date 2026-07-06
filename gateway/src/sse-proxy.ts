import { once } from "node:events";

import type { Request, Response } from "express";

import type { ChatStreamRequest } from "./schemas/chat.js";

export interface SSEProxyOptions {
  aiServiceUrl: string;
  correlationId: string;
  fetchImplementation: typeof fetch;
  payload: ChatStreamRequest;
  request: Request;
  requestId: string;
  response: Response;
  timeoutMs: number;
}

export interface NormalizedErrorBody {
  error: {
    code: string;
    correlation_id: string;
    message: string;
    request_id: string;
    retryable: boolean;
  };
}

export async function proxySSE(options: SSEProxyOptions): Promise<void> {
  const {
    aiServiceUrl,
    correlationId,
    fetchImplementation,
    payload,
    request,
    requestId,
    response,
    timeoutMs,
  } = options;
  const controller = new AbortController();
  let timedOut = false;
  let streamStarted = false;
  let lastSequence = 0;
  let terminalEventSeen = false;
  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
  const decoder = new TextDecoder();
  let inspectionBuffer = "";

  const timeout = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const abortForClientDisconnect = () => {
    if (!response.writableEnded) {
      controller.abort();
    }
  };
  request.once("aborted", abortForClientDisconnect);
  response.once("close", abortForClientDisconnect);

  const inspectChunk = (chunk: Uint8Array, final = false): void => {
    inspectionBuffer += decoder.decode(chunk, { stream: !final });
    const lines = inspectionBuffer.split(/\r?\n/);
    inspectionBuffer = final ? "" : (lines.pop() ?? "");
    for (const line of lines) {
      if (line.startsWith("id: ")) {
        const parsed = Number.parseInt(line.slice(4), 10);
        if (Number.isSafeInteger(parsed) && parsed > lastSequence) {
          lastSequence = parsed;
        }
      }
      if (line === "event: response.completed" || line === "event: error") {
        terminalEventSeen = true;
      }
    }
  };

  try {
    const upstream = await fetchImplementation(`${stripTrailingSlash(aiServiceUrl)}/api/v1/chat/stream`, {
      body: JSON.stringify(payload),
      headers: {
        Accept: "text/event-stream",
        "Content-Type": "application/json",
        "X-Correlation-ID": correlationId,
        "X-Request-ID": requestId,
      },
      method: "POST",
      signal: controller.signal,
    });
    const contentType = upstream.headers.get("content-type") ?? "";
    if (!upstream.ok) {
      await upstream.body?.cancel();
      sendNormalizedError(response, 502, {
        code: "AI_SERVICE_ERROR",
        correlationId,
        message: "The AI service rejected the streamed request.",
        requestId,
        retryable: upstream.status >= 500 || upstream.status === 429,
      });
      return;
    }
    if (!contentType.toLowerCase().startsWith("text/event-stream") || upstream.body === null) {
      await upstream.body?.cancel();
      sendNormalizedError(response, 502, {
        code: "INVALID_UPSTREAM_STREAM",
        correlationId,
        message: "The AI service returned an invalid streaming response.",
        requestId,
        retryable: true,
      });
      return;
    }

    streamStarted = true;
    response.status(200);
    response.set({
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "Content-Type": "text/event-stream; charset=utf-8",
      "X-Accel-Buffering": "no",
      "X-Correlation-ID": correlationId,
      "X-Request-ID": requestId,
    });
    response.flushHeaders();
    reader = upstream.body.getReader();
    while (!controller.signal.aborted) {
      const result = await reader.read();
      if (result.done) {
        inspectChunk(new Uint8Array(), true);
        if (!terminalEventSeen && !response.writableEnded) {
          writeSSEError(response, ++lastSequence, {
            code: "UPSTREAM_DISCONNECTED",
            correlationId,
            message: "The AI service stream ended unexpectedly.",
            requestId,
            retryable: true,
          });
        }
        response.end();
        return;
      }
      inspectChunk(result.value);
      if (!response.write(result.value)) {
        await Promise.race([once(response, "drain"), once(response, "close")]);
      }
    }
  } catch {
    if (response.writableEnded || response.destroyed || request.aborted) {
      return;
    }
    const error = {
      code: timedOut ? "UPSTREAM_TIMEOUT" : "UPSTREAM_DISCONNECTED",
      correlationId,
      message: timedOut
        ? "The AI service stream exceeded the gateway timeout."
        : "The gateway lost its connection to the AI service.",
      requestId,
      retryable: true,
    };
    if (streamStarted) {
      writeSSEError(response, ++lastSequence, error);
      response.end();
    } else {
      sendNormalizedError(response, timedOut ? 504 : 502, error);
    }
  } finally {
    clearTimeout(timeout);
    request.off("aborted", abortForClientDisconnect);
    response.off("close", abortForClientDisconnect);
    if (reader !== undefined) {
      try {
        await reader.cancel();
      } catch {
        // Reader cleanup is best-effort after a completed or failed upstream stream.
      }
      reader.releaseLock();
    }
  }
}

interface ErrorDetails {
  code: string;
  correlationId: string;
  message: string;
  requestId: string;
  retryable: boolean;
}

export function sendNormalizedError(
  response: Response,
  status: number,
  details: ErrorDetails,
): void {
  if (response.headersSent) {
    return;
  }
  const body: NormalizedErrorBody = {
    error: {
      code: details.code,
      correlation_id: details.correlationId,
      message: details.message,
      request_id: details.requestId,
      retryable: details.retryable,
    },
  };
  response.status(status).json(body);
}

function writeSSEError(response: Response, sequence: number, details: ErrorDetails): void {
  const data = JSON.stringify({
    code: details.code,
    correlation_id: details.correlationId,
    message: details.message,
    request_id: details.requestId,
    retryable: details.retryable,
    schema_version: "1.0",
    sequence,
    type: "error",
  });
  response.write(`id: ${sequence}\nevent: error\ndata: ${data}\n\n`);
}

function stripTrailingSlash(value: string): string {
  return value.endsWith("/") ? value.slice(0, -1) : value;
}
