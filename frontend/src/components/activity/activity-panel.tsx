import { Check, CircleDashed } from "lucide-react";

import type { WorkspaceStreamState } from "@/workspace/stream-state";

export function ActivityPanel({ state }: { state: WorkspaceStreamState }) {
  return (
    <section aria-label="Agent activity">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-100">Agent Activity</h2>
          <p className="mt-1 text-xs text-slate-500">Operational events only</p>
        </div>
        {state.phase !== "Idle" && state.phase !== "Complete" && state.phase !== "Error" ? (
          <CircleDashed className="h-4 w-4 animate-spin text-cyan-300" aria-label="Agent running" />
        ) : null}
      </div>

      {state.activity.length === 0 ? (
        <div className="mt-5 rounded-xl border border-dashed border-white/10 px-4 py-5 text-center">
          <p className="text-xs leading-5 text-slate-500">Route, tools, evidence counts, latency, and validation will appear here.</p>
        </div>
      ) : (
        <ol className="mt-5 space-y-0">
          {state.activity.map((item, index) => (
            <li className="relative grid grid-cols-[22px_1fr] gap-3 pb-5 last:pb-0" key={item.id}>
              {index < state.activity.length - 1 ? <span className="absolute left-[10px] top-5 h-[calc(100%-0.25rem)] w-px bg-white/[0.08]" aria-hidden="true" /> : null}
              <span className="relative z-10 grid h-[22px] w-[22px] place-items-center rounded-full border border-cyan-300/20 bg-slate-950 text-cyan-300">
                <Check className="h-3 w-3" aria-hidden="true" />
              </span>
              <div className="min-w-0 pt-0.5">
                <p className="text-xs font-medium text-slate-200">{item.label}</p>
                <p className="mt-1 truncate text-[11px] capitalize text-slate-500">{item.detail}</p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
