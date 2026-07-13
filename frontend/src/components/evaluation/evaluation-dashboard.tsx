import { Activity, DatabaseZap, Gauge, RefreshCw, Route, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { getRecentEvaluationSummaries } from "@/api/client";
import type { EvaluationSummary } from "@/api/schemas";

interface EvaluationDashboardProps {
  aiServiceUrl: string;
}

const percent = (value: number) => `${Math.round(value * 100)}%`;
const milliseconds = (value: number) => `${value.toFixed(1)} ms`;

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.025] p-4">
      <p className="text-[11px] uppercase tracking-[0.12em] text-slate-600">{label}</p>
      <p className="mt-2 text-xl font-semibold tracking-tight text-white">{value}</p>
    </div>
  );
}

export function EvaluationDashboard({ aiServiceUrl }: EvaluationDashboardProps) {
  const [summaries, setSummaries] = useState<EvaluationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setSummaries(await getRecentEvaluationSummaries(aiServiceUrl));
    } catch {
      setError("Evaluation summaries are unavailable. Run the local evaluation CLI first.");
    } finally {
      setLoading(false);
    }
  }, [aiServiceUrl]);

  useEffect(() => {
    let active = true;
    void getRecentEvaluationSummaries(aiServiceUrl)
      .then((result) => {
        if (active) setSummaries(result);
      })
      .catch(() => {
        if (active) {
          setError("Evaluation summaries are unavailable. Run the local evaluation CLI first.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [aiServiceUrl]);

  const latest = summaries[0];
  return (
    <main className="mx-auto min-h-[calc(100vh-4rem)] max-w-[1440px] px-4 pb-24 pt-6 sm:px-6 lg:px-8 lg:pb-8" aria-labelledby="evaluation-title">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-cyan-300/70">Internal quality observatory</p>
          <h1 id="evaluation-title" className="mt-2 text-2xl font-semibold tracking-[-0.025em] text-white sm:text-3xl">Evaluation & observability</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-500">Reproducible retrieval, routing, grounding, safety, and runtime measurements. Operational aggregates only—no private reasoning is recorded.</p>
        </div>
        <button className="flex h-9 items-center gap-2 rounded-lg border border-white/[0.09] bg-white/[0.035] px-3 text-xs text-slate-300 transition hover:bg-white/[0.07]" onClick={() => void load()} type="button"><RefreshCw className="h-3.5 w-3.5" />Refresh</button>
      </div>

      {loading ? <div className="mt-8 h-56 animate-pulse rounded-2xl border border-white/[0.06] bg-white/[0.025]" /> : null}
      {!loading && error ? <div className="mt-8 rounded-2xl border border-amber-300/15 bg-amber-300/[0.04] p-6 text-sm text-amber-100/70">{error}</div> : null}
      {!loading && !error && !latest ? <div className="mt-8 rounded-2xl border border-dashed border-white/[0.1] p-10 text-center"><Gauge className="mx-auto h-6 w-6 text-slate-600" /><p className="mt-3 text-sm text-slate-400">No evaluation runs yet</p><p className="mt-1 text-xs text-slate-600">Run <code className="text-slate-400">python -m app.evaluation.run</code> from ai-service.</p></div> : null}

      {latest ? (
        <div className="mt-8 space-y-5">
          <section className="rounded-2xl border border-white/[0.07] bg-[#0b111d] p-5">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.06] pb-4">
              <div><p className="text-sm font-medium text-white">Latest completed run</p><p className="mt-1 text-xs text-slate-600">{latest.run_id} · {new Date(latest.timestamp).toLocaleString()}</p></div>
              <div className="text-right"><p className="text-xs text-cyan-200">{latest.provider} / {latest.model_identifier}</p><p className="mt-1 text-[10px] uppercase tracking-wider text-slate-600">{latest.configuration.dataset_id} v{latest.configuration.dataset_version}</p></div>
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <Metric label={`Hybrid recall@${latest.retrieval.k}`} value={percent(latest.retrieval.hybrid.recall_at_k)} />
              <Metric label="Hybrid MRR" value={percent(latest.retrieval.hybrid.mrr)} />
              <Metric label="Route accuracy" value={percent(latest.routing.route_accuracy)} />
              <Metric label="Answer relevance" value={percent(latest.generation.answer_relevance_proxy)} />
            </div>
          </section>

          <div className="grid gap-5 xl:grid-cols-2">
            <section className="rounded-2xl border border-white/[0.07] bg-[#0b111d] p-5">
              <h2 className="flex items-center gap-2 text-sm font-medium text-white"><DatabaseZap className="h-4 w-4 text-cyan-300" />Retrieval & generation</h2>
              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                <Metric label="Vector recall" value={percent(latest.retrieval.vector_only.recall_at_k)} />
                <Metric label="Hybrid latency" value={milliseconds(latest.retrieval.hybrid.average_latency_ms)} />
                <Metric label="Groundedness" value={percent(latest.generation.groundedness)} />
                <Metric label="Citation coverage" value={percent(latest.generation.citation_coverage)} />
                <Metric label="Tool selection" value={percent(latest.routing.tool_selection_accuracy)} />
                <Metric label="Retrieval cases" value={String(latest.retrieval.query_count)} />
              </div>
            </section>
            <section className="rounded-2xl border border-white/[0.07] bg-[#0b111d] p-5">
              <h2 className="flex items-center gap-2 text-sm font-medium text-white"><ShieldCheck className="h-4 w-4 text-emerald-300" />Guardrail benchmark</h2>
              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
                <Metric label="Injection accuracy" value={percent(latest.guardrails.injection_detection_accuracy)} />
                <Metric label="Claim detection" value={percent(latest.guardrails.unsupported_claim_detection_accuracy)} />
                <Metric label="Block rate" value={percent(latest.guardrails.block_rate)} />
                <Metric label="Rewrite rate" value={percent(latest.guardrails.rewrite_rate)} />
                <Metric label="Guard cases" value={String(latest.guardrails.case_count)} />
              </div>
            </section>
          </div>

          <section className="rounded-2xl border border-white/[0.07] bg-[#0b111d] p-5">
            <h2 className="flex items-center gap-2 text-sm font-medium text-white"><Activity className="h-4 w-4 text-violet-300" />System telemetry</h2>
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
              <Metric label="Total latency" value={milliseconds(latest.system.total_latency_ms)} />
              <Metric label="Retrieval" value={milliseconds(latest.system.retrieval_latency_ms)} />
              <Metric label="Generation" value={milliseconds(latest.system.generation_latency_ms)} />
              <Metric label="Guardrails" value={milliseconds(latest.system.guardrail_latency_ms)} />
              <Metric label="Provider calls" value={String(latest.system.provider_calls)} />
              <Metric label="Est. tokens" value={String(latest.system.estimated_token_usage)} />
            </div>
            <p className="mt-4 flex items-center gap-2 text-[11px] text-slate-600"><Route className="h-3.5 w-3.5" />Configuration fingerprint {latest.configuration.fingerprint.slice(0, 16)} · deterministic seed {latest.configuration.random_seed}</p>
          </section>
        </div>
      ) : null}
    </main>
  );
}
