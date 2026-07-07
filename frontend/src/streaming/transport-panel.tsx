import { useEffect, useRef, useState, type FormEvent } from "react";

import type { GenUIComponent } from "../../../shared/genui.js";
import type { StreamEvent } from "../../../shared/streaming.js";
import { GenUIRenderer } from "@/genui/renderer";
import { streamChat } from "@/streaming/client";

interface StreamingTransportPanelProps {
  gatewayUrl: string;
}

export function StreamingTransportPanel({ gatewayUrl }: StreamingTransportPanelProps) {
  const [message, setMessage] = useState("Explain what RAG means.");
  const [answer, setAnswer] = useState("");
  const [status, setStatus] = useState("Idle");
  const [route, setRoute] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [components, setComponents] = useState<GenUIComponent[]>([]);
  const activeRequest = useRef<AbortController | null>(null);

  useEffect(
    () => () => {
      activeRequest.current?.abort();
    },
    [],
  );

  const handleEvent = (event: StreamEvent): void => {
    switch (event.type) {
      case "request.started":
        setStatus("Request accepted");
        break;
      case "route.selected":
        setRoute(event.route);
        setStatus("Route selected");
        break;
      case "retrieval.started":
        setStatus(`Retrieving with ${event.tool}`);
        break;
      case "retrieval.completed":
        setStatus(`Retrieved ${event.candidate_count} candidate(s)`);
        break;
      case "generation.started":
        setStatus("Generating safe response");
        break;
      case "generation.token":
        setAnswer((current) => current + event.token);
        break;
      case "genui.created":
        setComponents(event.components);
        break;
      case "guardrail.completed":
        setStatus(`Guardrail: ${event.result.decision}`);
        break;
      case "response.completed":
        setAnswer(event.final_response);
        setStatus(`Completed in ${event.latency_ms} ms`);
        break;
      case "error":
        setError(event.message);
        setStatus("Stream failed");
        break;
    }
  };

  const submit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const normalized = message.trim();
    if (!normalized) return;
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setAnswer("");
    setComponents([]);
    setError(null);
    setRoute(null);
    setStatus("Connecting");
    const threadId = `stream-${globalThis.crypto.randomUUID()}`;
    void streamChat({
      gatewayUrl,
      onEvent: handleEvent,
      request: { message: normalized, thread_id: threadId },
      signal: controller.signal,
    }).catch((streamError: unknown) => {
      if (controller.signal.aborted) return;
      setError(streamError instanceof Error ? streamError.message : "The stream failed.");
      setStatus("Stream failed");
    });
  };

  return (
    <section className="mt-6 rounded-2xl border border-white/10 bg-slate-900/50 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="font-medium text-white">SSE transport check</h2>
          <p className="mt-1 text-sm text-slate-400">
            React fetch stream → Express proxy → FastAPI graph
          </p>
        </div>
        <span className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs text-cyan-100">
          {status}
        </span>
      </div>
      <form className="mt-5 flex flex-col gap-3 sm:flex-row" onSubmit={submit}>
        <label className="sr-only" htmlFor="stream-message">
          Streaming prompt
        </label>
        <input
          id="stream-message"
          className="min-w-0 flex-1 rounded-xl border border-white/10 bg-slate-950 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-300/50"
          maxLength={4_000}
          onChange={(event) => setMessage(event.target.value)}
          value={message}
        />
        <button
          className="rounded-xl bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200"
          type="submit"
        >
          Stream response
        </button>
      </form>
      {route ? <p className="mt-4 text-xs text-slate-500">Selected route: {route}</p> : null}
      {error ? (
        <p className="mt-4 rounded-xl border border-rose-400/20 bg-rose-400/10 p-4 text-sm text-rose-100">
          {error}
        </p>
      ) : null}
      {answer ? (
        <p className="mt-4 whitespace-pre-wrap rounded-xl border border-white/10 bg-slate-950/80 p-4 text-sm leading-6 text-slate-200">
          {answer}
        </p>
      ) : null}
      {components.length ? (
        <div className="mt-4 space-y-4">
          {components.map((component, index) => (
            <GenUIRenderer
              key={`${component.type}-${index}`}
              payload={component}
              fallbackText="The streamed visualization was invalid; the safe answer remains visible."
            />
          ))}
        </div>
      ) : null}
    </section>
  );
}
