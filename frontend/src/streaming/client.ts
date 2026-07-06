import { streamEventSchema, type StreamEvent } from "../../../shared/streaming.js";

export interface StreamChatRequest {
  message: string;
  thread_id: string;
}

export interface StreamChatOptions {
  fetchImplementation?: typeof fetch;
  gatewayUrl: string;
  onEvent: (event: StreamEvent) => void;
  request: StreamChatRequest;
  signal?: AbortSignal;
}

export class StreamProtocolError extends Error {
  public constructor(message: string) {
    super(message);
    this.name = "StreamProtocolError";
  }
}

export async function streamChat(options: StreamChatOptions): Promise<void> {
  const fetchImplementation = options.fetchImplementation ?? fetch;
  const response = await fetchImplementation(
    `${options.gatewayUrl.replace(/\/$/, "")}/api/v1/chat/stream`,
    {
      body: JSON.stringify(options.request),
      headers: {
        Accept: "text/event-stream",
        "Content-Type": "application/json",
      },
      method: "POST",
      ...(options.signal ? { signal: options.signal } : {}),
    },
  );
  if (!response.ok) {
    throw new StreamProtocolError(`Streaming request failed with status ${response.status}.`);
  }
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.toLowerCase().startsWith("text/event-stream")) {
    throw new StreamProtocolError("Gateway returned a non-SSE response.");
  }
  await parseSSEStream(response, options.onEvent, options.signal);
}

export async function parseSSEStream(
  response: Response,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  if (response.body === null) {
    throw new StreamProtocolError("SSE response did not contain a readable body.");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let eventName = "";
  let eventId = "";
  let dataLines: string[] = [];

  const dispatch = (): void => {
    if (dataLines.length === 0) {
      eventName = "";
      eventId = "";
      return;
    }
    let raw: unknown;
    try {
      raw = JSON.parse(dataLines.join("\n"));
    } catch {
      throw new StreamProtocolError("SSE event data was not valid JSON.");
    }
    const parsed = streamEventSchema.safeParse(raw);
    if (!parsed.success) {
      throw new StreamProtocolError("SSE event failed schema validation.");
    }
    if (eventName !== parsed.data.type || eventId !== String(parsed.data.sequence)) {
      throw new StreamProtocolError("SSE envelope did not match its typed event data.");
    }
    onEvent(parsed.data);
    eventName = "";
    eventId = "";
    dataLines = [];
  };

  const consumeLines = (final: boolean): void => {
    const lines = buffer.split(/\r?\n/);
    buffer = final ? "" : (lines.pop() ?? "");
    for (const line of lines) {
      if (line === "") {
        dispatch();
      } else if (!line.startsWith(":")) {
        const separator = line.indexOf(":");
        const field = separator === -1 ? line : line.slice(0, separator);
        const value = separator === -1 ? "" : line.slice(separator + 1).replace(/^ /, "");
        if (field === "event") eventName = value;
        if (field === "id") eventId = value;
        if (field === "data") dataLines.push(value);
      }
    }
  };

  try {
    while (true) {
      if (signal?.aborted) {
        await reader.cancel();
        return;
      }
      const result = await reader.read();
      if (result.done) {
        buffer += decoder.decode();
        consumeLines(true);
        dispatch();
        return;
      }
      buffer += decoder.decode(result.value, { stream: true });
      consumeLines(false);
    }
  } finally {
    reader.releaseLock();
  }
}
