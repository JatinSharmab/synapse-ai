import { Gauge, ShieldCheck } from "lucide-react";

import type { WorkspaceStreamState } from "@/workspace/stream-state";

function percentage(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function QualitySummary({ state }: { state: WorkspaceStreamState }) {
  const quality = state.quality;
  return (
    <section aria-label="Response quality">
      <div className="flex items-center gap-2.5">
        <Gauge className="h-4 w-4 text-violet-300" aria-hidden="true" />
        <div>
          <h2 className="text-sm font-semibold text-slate-100">Response Quality</h2>
          <p className="mt-1 text-xs text-slate-500">Live Sentinel evaluation</p>
        </div>
      </div>
      {!quality ? (
        <p className="mt-5 rounded-xl border border-dashed border-white/10 px-4 py-5 text-center text-xs leading-5 text-slate-500">
          Grounding and citation coverage appear after validation.
        </p>
      ) : (
        <div className="mt-5 space-y-4">
          {[
            ["Groundedness", percentage(quality.groundedness), quality.groundedness],
            ["Citation coverage", percentage(quality.citationCoverage), quality.citationCoverage],
          ].map(([label, display, value]) => (
            <div key={String(label)}>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">{label}</span>
                <span className="font-mono text-slate-200">{display}</span>
              </div>
              <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/[0.06]">
                <div className="h-full rounded-full bg-cyan-300" style={{ width: `${Number(value) * 100}%` }} />
              </div>
            </div>
          ))}
          <div className="grid grid-cols-2 gap-2 border-t border-white/[0.07] pt-4 text-xs">
            <div className="rounded-lg bg-white/[0.035] p-3">
              <p className="text-slate-500">Decision</p>
              <p className="mt-1 capitalize text-emerald-300">{quality.decision}</p>
            </div>
            <div className="rounded-lg bg-white/[0.035] p-3">
              <p className="text-slate-500">Latency</p>
              <p className="mt-1 font-mono text-slate-200">{quality.latencyMs === null ? "—" : `${quality.latencyMs} ms`}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-[11px] text-slate-500">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-300" aria-hidden="true" />
            Schema {quality.schemaValid ? "valid" : "invalid"} · rewrites {quality.rewriteCount}/1
          </div>
        </div>
      )}
    </section>
  );
}
