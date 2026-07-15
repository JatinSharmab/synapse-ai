import { BrainCircuit, Gauge, Library, MessageSquareText } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { AIWorkspace } from "@/components/chat/ai-workspace";
import { KnowledgeLibrary } from "@/components/knowledge/knowledge-library";
import { EvaluationDashboard } from "@/components/evaluation/evaluation-dashboard";
import { SystemStatus } from "@/components/system/system-status";
import { runtimeConfig } from "@/config";
import { cn } from "@/lib/utils";

type View = "workspace" | "knowledge" | "evaluation";

const navigation = [
  { icon: MessageSquareText, label: "AI Workspace", value: "workspace" as const },
  { icon: Library, label: "Knowledge", value: "knowledge" as const },
  { icon: Gauge, label: "Evaluation", value: "evaluation" as const },
];

const viewTitles: Record<View, string> = {
  workspace: "AI Workspace",
  knowledge: "Knowledge Library",
  evaluation: "Evaluation & Observability",
};

export function App() {
  const [view, setView] = useState<View>("workspace");
  const [videoUrls, setVideoUrls] = useState<Record<string, string>>({});
  const videoUrlsRef = useRef<Record<string, string>>({});

  useEffect(() => () => Object.values(videoUrlsRef.current).forEach((url) => URL.revokeObjectURL(url)), []);

  const registerVideo = (videoId: string, filename: string, sourceUrl: string) => {
    const next = { ...videoUrlsRef.current, [filename]: sourceUrl, [videoId]: sourceUrl };
    videoUrlsRef.current = next;
    setVideoUrls(next);
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="noise pointer-events-none fixed inset-0 z-50 opacity-[0.018]" aria-hidden="true" />
      <div className="grid min-h-screen grid-cols-[minmax(0,1fr)] lg:grid-cols-[72px_minmax(0,1fr)] xl:grid-cols-[232px_minmax(0,1fr)]">
        <aside className="fixed inset-y-0 left-0 z-40 hidden w-[72px] flex-col border-r border-white/[0.07] bg-[#070c15]/95 px-3 py-4 backdrop-blur-xl lg:flex xl:w-[232px] xl:px-4" aria-label="Primary navigation">
          <div className="flex h-10 items-center gap-3 px-1.5 xl:px-2">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl border border-cyan-300/20 bg-cyan-300/[0.07] text-cyan-200"><BrainCircuit className="h-[18px] w-[18px]" aria-hidden="true" /></span>
            <div className="hidden min-w-0 xl:block"><p className="text-[13px] font-semibold tracking-[0.19em] text-white">SYNAPSE</p><p className="mt-0.5 truncate text-[10px] text-slate-600">Intelligence OS</p></div>
          </div>
          <nav className="mt-9 space-y-1">
            {navigation.map(({ icon: Icon, label, value }) => (
              <button aria-current={view === value ? "page" : undefined} className={cn("group flex h-11 w-full items-center gap-3 rounded-xl px-3 text-sm transition", view === value ? "bg-white/[0.07] text-white" : "text-slate-500 hover:bg-white/[0.04] hover:text-slate-300")} key={value} onClick={() => setView(value)} title={label} type="button">
                <Icon className={cn("h-[18px] w-[18px] shrink-0", view === value && "text-cyan-300")} aria-hidden="true" /><span className="hidden xl:inline">{label}</span>
              </button>
            ))}
          </nav>
          <div className="mt-auto hidden rounded-2xl border border-white/[0.07] bg-white/[0.025] p-4 xl:block">
            <SystemStatus aiServiceUrl={runtimeConfig.aiServiceUrl} gatewayUrl={runtimeConfig.gatewayUrl} />
          </div>
          <span className="mx-auto mt-auto hidden h-2 w-2 rounded-full bg-emerald-400 lg:block xl:hidden" title="Readiness available in the header" />
        </aside>

        <div className="min-w-0 lg:col-start-2">
          <header className="sticky top-0 z-30 flex h-16 items-center border-b border-white/[0.07] bg-[#080d17]/90 px-4 backdrop-blur-xl sm:px-6">
            <div className="flex items-center gap-3 lg:hidden">
              <span className="grid h-8 w-8 place-items-center rounded-lg border border-cyan-300/15 bg-cyan-300/[0.06] text-cyan-200"><BrainCircuit className="h-4 w-4" /></span>
              <div><p className="text-[12px] font-semibold tracking-[0.16em] text-white">SYNAPSE</p><p className="text-[9px] text-slate-600">Enterprise AI Intelligence OS</p></div>
            </div>
            <p className="hidden text-xs text-slate-500 lg:block">Enterprise AI Intelligence OS <span className="mx-2 text-slate-800">/</span> <span className="text-slate-300">{viewTitles[view]}</span></p>
          </header>

          {view === "workspace" ? (
            <AIWorkspace gatewayUrl={runtimeConfig.gatewayUrl} videoUrls={videoUrls} />
          ) : view === "knowledge" ? (
            <KnowledgeLibrary aiServiceUrl={runtimeConfig.aiServiceUrl} gatewayUrl={runtimeConfig.gatewayUrl} directUploadsEnabled={runtimeConfig.directUploadsEnabled} onVideoAvailable={registerVideo} />
          ) : (
            <EvaluationDashboard aiServiceUrl={runtimeConfig.aiServiceUrl} />
          )}
        </div>
      </div>

      <nav className="fixed inset-x-3 bottom-3 z-40 grid grid-cols-3 rounded-2xl border border-white/[0.10] bg-[#0a101b]/95 p-1.5 shadow-2xl backdrop-blur-xl lg:hidden" aria-label="Mobile navigation">
        {navigation.map(({ icon: Icon, label, value }) => (
          <button className={cn("flex h-11 items-center justify-center gap-2 rounded-xl text-xs transition", view === value ? "bg-white/[0.07] text-white" : "text-slate-500")} key={value} onClick={() => setView(value)} type="button"><Icon className={cn("h-4 w-4", view === value && "text-cyan-300")} />{label}</button>
        ))}
      </nav>
    </div>
  );
}
