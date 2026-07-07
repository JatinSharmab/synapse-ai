import type { GenUIComponent } from "../../../shared/genui.js";
import type { StreamEvent } from "../../../shared/streaming.js";

export type StreamPhase =
  | "Idle"
  | "Thinking"
  | "Routing"
  | "Searching Documents"
  | "Searching Video"
  | "Analyzing Data"
  | "Synthesizing"
  | "Validating"
  | "Complete"
  | "Error";

export interface ActivityItem {
  detail: string;
  id: string;
  label: string;
  phase: StreamPhase;
}

export interface WorkspaceStreamState {
  activity: ActivityItem[];
  answer: string;
  citations: Extract<StreamEvent, { type: "response.completed" }>["citations"];
  components: GenUIComponent[];
  error: string | null;
  phase: StreamPhase;
  quality: {
    citationCoverage: number;
    decision: "approve" | "rewrite" | "block";
    groundedness: number;
    latencyMs: number | null;
    rewriteCount: number;
    schemaValid: boolean;
  } | null;
  route: Extract<StreamEvent, { type: "route.selected" }>["route"] | null;
}

export function initialStreamState(): WorkspaceStreamState {
  return {
    activity: [],
    answer: "",
    citations: [],
    components: [],
    error: null,
    phase: "Idle",
    quality: null,
    route: null,
  };
}

function activity(event: StreamEvent, phase: StreamPhase, label: string, detail: string): ActivityItem {
  return { detail, id: `${event.request_id}-${event.sequence}`, label, phase };
}

export function applyStreamEvent(
  state: WorkspaceStreamState,
  event: StreamEvent,
): WorkspaceStreamState {
  switch (event.type) {
    case "request.started":
      return {
        ...state,
        phase: "Thinking",
        activity: [...state.activity, activity(event, "Thinking", "Request accepted", `Thread ${event.thread_id}`)],
      };
    case "route.selected": {
      const phase = event.route === "data_analytics" ? "Analyzing Data" : "Routing";
      return {
        ...state,
        phase,
        route: event.route,
        activity: [...state.activity, activity(event, phase, "Route selected", event.route.replaceAll("_", " "))],
      };
    }
    case "retrieval.started": {
      const phase = event.tool === "document_search" ? "Searching Documents" : "Searching Video";
      return {
        ...state,
        phase,
        activity: [...state.activity, activity(event, phase, "Evidence search started", event.tool.replaceAll("_", " "))],
      };
    }
    case "retrieval.completed": {
      const phase = event.tool === "document_search" ? "Searching Documents" : "Searching Video";
      return {
        ...state,
        phase,
        activity: [
          ...state.activity,
          activity(event, phase, "Evidence search completed", `${event.candidate_count} candidates · ${event.latency_ms} ms`),
        ],
      };
    }
    case "generation.started":
      return {
        ...state,
        phase: "Synthesizing",
        activity: [...state.activity, activity(event, "Synthesizing", "Answer synthesis started", event.route.replaceAll("_", " "))],
      };
    case "generation.token":
      return { ...state, answer: state.answer + event.token, phase: "Synthesizing" };
    case "genui.created":
      return {
        ...state,
        components: event.components,
        activity: [...state.activity, activity(event, "Synthesizing", "Visual output validated", `${event.components.length} component(s)`)],
      };
    case "guardrail.completed":
      return {
        ...state,
        phase: "Validating",
        quality: {
          citationCoverage: event.result.citation_coverage,
          decision: event.result.decision,
          groundedness: event.result.groundedness_score,
          latencyMs: null,
          rewriteCount: event.rewrite_count,
          schemaValid: event.result.schema_valid,
        },
        activity: [
          ...state.activity,
          activity(event, "Validating", "Sentinel validation completed", `${event.result.decision} · rewrite ${event.rewrite_count}/1`),
        ],
      };
    case "response.completed":
      return {
        ...state,
        answer: event.final_response,
        citations: event.citations,
        phase: "Complete",
        quality: state.quality
          ? { ...state.quality, latencyMs: event.latency_ms, rewriteCount: event.rewrite_count }
          : null,
        activity: [
          ...state.activity,
          activity(event, "Complete", "Response completed", `${event.citation_count} citations · ${event.latency_ms} ms`),
        ],
      };
    case "error":
      return {
        ...state,
        error: event.message,
        phase: "Error",
        activity: [...state.activity, activity(event, "Error", "Request stopped", `${event.code} · ${event.retryable ? "retryable" : "not retryable"}`)],
      };
  }
}
