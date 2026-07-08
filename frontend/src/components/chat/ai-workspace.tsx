import {
  ArrowUp,
  BookOpen,
  BrainCircuit,
  FileSearch,
  LoaderCircle,
  PanelRightOpen,
  ShieldCheck,
  Sparkles,
  Square,
} from "lucide-react";
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { ActivityPanel } from "@/components/activity/activity-panel";
import { EvidencePanel } from "@/components/evidence/evidence-panel";
import { SourceDrawer } from "@/components/evidence/source-drawer";
import type { VideoEvidenceSelection } from "@/components/evidence/video-evidence-player";
import { Panel } from "@/components/ui/panel";
import { QualitySummary } from "@/components/quality/quality-summary";
import { GenUIRenderer, type VideoEvidenceItem } from "@/genui/renderer";
import { cn } from "@/lib/utils";
import { streamChat } from "@/streaming/client";
import { applyStreamEvent, initialStreamState, type StreamPhase } from "@/workspace/stream-state";

const suggestions = [
  { icon: FileSearch, label: "Find a policy", prompt: "Find the refund policy in my documents." },
  { icon: BookOpen, label: "Review video", prompt: "What happened at 2 minutes in the uploaded video?" },
  { icon: Sparkles, label: "Analyze revenue", prompt: "Compare revenue across regions." },
  { icon: BrainCircuit, label: "Explain a concept", prompt: "Explain what RAG means." },
];

const activePhases: StreamPhase[] = ["Thinking", "Routing", "Searching Documents", "Searching Video", "Analyzing Data", "Synthesizing", "Validating"];

interface AIWorkspaceProps {
  gatewayUrl: string;
  videoUrls: Readonly<Record<string, string>>;
}

function videoSelection(item: VideoEvidenceItem): VideoEvidenceSelection {
  return {
    description: item.description,
    endSeconds: item.end_seconds,
    filename: item.filename,
    segmentId: item.segment_id,
    startSeconds: item.start_seconds,
    videoId: item.video_id,
  };
}

export function AIWorkspace({ gatewayUrl, videoUrls }: AIWorkspaceProps) {
  const [prompt, setPrompt] = useState("");
  const [question, setQuestion] = useState<string | null>(null);
  const [streamState, setStreamState] = useState(initialStreamState);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedVideo, setSelectedVideo] = useState<VideoEvidenceSelection | null>(null);
  const activeRequest = useRef<AbortController | null>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const running = activePhases.includes(streamState.phase);

  useEffect(() => () => activeRequest.current?.abort(), []);

  const openVideo = (selection: VideoEvidenceSelection) => {
    setSelectedVideo(selection);
    setDrawerOpen(true);
  };

  const submitPrompt = (value: string) => {
    const message = value.trim();
    if (!message || running) return;
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setQuestion(message);
    setPrompt("");
    setSelectedVideo(null);
    setStreamState({ ...initialStreamState(), phase: "Thinking" });
    const threadId = `workspace-${globalThis.crypto.randomUUID()}`;
    void streamChat({
      gatewayUrl,
      onEvent: (event) => setStreamState((current) => applyStreamEvent(current, event)),
      request: { message, thread_id: threadId },
      signal: controller.signal,
    }).catch((error: unknown) => {
      if (controller.signal.aborted) return;
      setStreamState((current) => ({
        ...current,
        error: error instanceof Error ? error.message : "The request could not be completed.",
        phase: "Error",
      }));
    });
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    submitPrompt(prompt);
  };

  const onComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitPrompt(prompt);
    }
  };

  const selectedVideoUrl = selectedVideo
    ? videoUrls[selectedVideo.videoId] ?? videoUrls[selectedVideo.filename]
    : undefined;

  return (
    <div className="grid min-h-[calc(100vh-4rem)] min-w-0 grid-cols-[minmax(0,1fr)] xl:grid-cols-[minmax(0,1fr)_340px]">
      <main className="relative min-w-0 border-white/[0.07] xl:border-r" aria-label="AI chat workspace">
        <div className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-4xl flex-col px-4 pb-32 pt-5 sm:px-7 lg:px-10 lg:pt-9">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="eyebrow">Intelligence workspace</p>
              <h1 className="mt-1.5 text-xl font-semibold tracking-[-0.025em] text-white sm:text-2xl">Ask across your enterprise knowledge</h1>
            </div>
            <button className="inline-flex min-h-9 items-center gap-2 rounded-xl border border-white/[0.08] bg-white/[0.035] px-3 text-xs text-slate-400 transition hover:text-white xl:hidden" onClick={() => setDrawerOpen(true)} type="button">
              <PanelRightOpen className="h-3.5 w-3.5" aria-hidden="true" /> Sources {streamState.citations.length ? `(${streamState.citations.length})` : ""}
            </button>
          </div>

          {!question ? (
            <section className="my-auto py-16 sm:py-24" aria-label="AI workspace empty state">
              <div className="max-w-2xl">
                <span className="grid h-11 w-11 place-items-center rounded-2xl border border-cyan-300/20 bg-cyan-300/[0.07] text-cyan-200"><BrainCircuit className="h-5 w-5" aria-hidden="true" /></span>
                <h2 className="mt-6 max-w-xl text-3xl font-semibold leading-tight tracking-[-0.035em] text-white sm:text-4xl">Intelligence, grounded in what your organization knows.</h2>
                <p className="mt-4 max-w-xl text-sm leading-7 text-slate-400">Search documents, inspect video moments, and analyze governed datasets through one secure workspace.</p>
              </div>
              <div className="mt-9 grid gap-2 sm:grid-cols-2">
                {suggestions.map(({ icon: Icon, label, prompt: suggestion }) => (
                  <button className="group flex items-center gap-3 rounded-xl border border-white/[0.07] bg-white/[0.025] px-4 py-3.5 text-left transition hover:border-cyan-300/20 hover:bg-white/[0.045]" key={label} onClick={() => submitPrompt(suggestion)} type="button">
                    <Icon className="h-4 w-4 shrink-0 text-slate-500 transition group-hover:text-cyan-300" aria-hidden="true" />
                    <span><span className="block text-xs font-medium text-slate-300">{label}</span><span className="mt-0.5 block truncate text-[11px] text-slate-600">{suggestion}</span></span>
                  </button>
                ))}
              </div>
            </section>
          ) : (
            <section className="mt-10 flex-1" aria-live="polite">
              <div className="ml-auto max-w-[82%] rounded-2xl rounded-tr-md border border-white/[0.07] bg-white/[0.045] px-4 py-3 text-sm leading-6 text-slate-200 sm:max-w-[72%]">{question}</div>
              <article className="mt-8">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5"><span className="grid h-7 w-7 place-items-center rounded-lg bg-cyan-300/[0.08] text-cyan-200"><BrainCircuit className="h-3.5 w-3.5" aria-hidden="true" /></span><span className="text-xs font-semibold text-slate-300">Synapse</span></div>
                  <span className={cn("inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[10px] font-medium", streamState.phase === "Complete" ? "border-emerald-300/15 bg-emerald-300/[0.05] text-emerald-300" : streamState.phase === "Error" ? "border-rose-300/15 bg-rose-300/[0.05] text-rose-300" : "border-cyan-300/15 bg-cyan-300/[0.05] text-cyan-200")}>
                    {running ? <LoaderCircle className="h-3 w-3 animate-spin" aria-hidden="true" /> : null}{streamState.phase}
                  </span>
                </div>
                {streamState.error ? <p className="rounded-xl border border-rose-300/15 bg-rose-300/[0.05] px-4 py-3 text-sm text-rose-200">{streamState.error}</p> : null}
                {streamState.answer ? (
                  <p className="whitespace-pre-wrap text-[15px] leading-8 text-slate-200">{streamState.answer}</p>
                ) : running ? (
                  <div className="space-y-3 py-2"><div className="h-3 w-11/12 animate-pulse rounded bg-white/[0.07]" /><div className="h-3 w-4/5 animate-pulse rounded bg-white/[0.06]" /><div className="h-3 w-3/5 animate-pulse rounded bg-white/[0.05]" /><p className="pt-2 text-xs text-slate-600">Secure services may take a moment to wake from a cold start.</p></div>
                ) : null}
                {streamState.citations.length ? (
                  <button className="mt-5 inline-flex items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-xs text-slate-400 transition hover:text-white" onClick={() => setDrawerOpen(true)} type="button"><BookOpen className="h-3.5 w-3.5 text-cyan-300" /> {streamState.citations.length} grounded source{streamState.citations.length === 1 ? "" : "s"}</button>
                ) : null}
              </article>

              {streamState.components.length ? (
                <section className="mt-10 space-y-4" aria-label="Generated visual output">
                  <div className="flex items-center gap-2 text-xs font-medium text-slate-400"><Sparkles className="h-3.5 w-3.5 text-violet-300" /> Validated visual output</div>
                  {streamState.components.map((component, index) => <GenUIRenderer fallbackText="The visual response could not be safely rendered. The answer above remains available." key={`${component.type}-${index}`} onVideoEvidence={(item) => openVideo(videoSelection(item))} payload={component} />)}
                </section>
              ) : null}

              <div className="mt-10 grid gap-4 md:grid-cols-2 xl:hidden">
                <Panel className="p-5"><ActivityPanel state={streamState} /></Panel>
                <Panel className="p-5"><QualitySummary state={streamState} /></Panel>
              </div>
            </section>
          )}

          <form className="fixed bottom-[4.5rem] left-3 right-3 z-30 mx-auto max-w-3xl lg:bottom-5 lg:left-[5.5rem] xl:left-[15.5rem] xl:right-[21.75rem]" onSubmit={submit}>
            <div className="rounded-2xl border border-white/[0.10] bg-[#0b111d]/95 p-2 shadow-[0_20px_70px_rgba(0,0,0,.45)] backdrop-blur-xl focus-within:border-cyan-300/25">
              <label className="sr-only" htmlFor="synapse-prompt">Ask Synapse</label>
              <textarea className="max-h-32 min-h-12 w-full resize-none bg-transparent px-3 py-3 text-sm leading-6 text-slate-100 outline-none placeholder:text-slate-600" id="synapse-prompt" maxLength={4_000} onChange={(event) => setPrompt(event.target.value)} onKeyDown={onComposerKeyDown} placeholder="Ask across documents, video, and data…" ref={textarea} rows={1} value={prompt} />
              <div className="flex items-center justify-between px-2 pb-1">
                <span className="text-[10px] text-slate-600">Enter to send · Shift + Enter for a new line</span>
                {running ? (
                  <button aria-label="Stop response" className="grid h-8 w-8 place-items-center rounded-lg bg-white/[0.08] text-slate-300 transition hover:bg-white/[0.12]" onClick={() => activeRequest.current?.abort()} type="button"><Square className="h-3 w-3 fill-current" /></button>
                ) : (
                  <button aria-label="Send message" className="grid h-8 w-8 place-items-center rounded-lg bg-cyan-300 text-slate-950 transition hover:bg-cyan-200 disabled:opacity-35" disabled={!prompt.trim()} type="submit"><ArrowUp className="h-4 w-4" /></button>
                )}
              </div>
            </div>
            <p className="mt-2 text-center text-[10px] text-slate-700"><ShieldCheck className="mr-1 inline h-3 w-3" />Answers pass grounding and output validation. Verify critical decisions.</p>
          </form>
        </div>
      </main>

      <aside className="hidden h-[calc(100vh-4rem)] overflow-y-auto bg-slate-950/25 xl:block" aria-label="Evidence and execution details">
        <div className="divide-y divide-white/[0.07]">
          <div className="p-6"><EvidencePanel citations={streamState.citations} onOpenVideo={openVideo} /></div>
          <div className="p-6"><ActivityPanel state={streamState} /></div>
          <div className="p-6"><QualitySummary state={streamState} /></div>
        </div>
      </aside>

      <SourceDrawer citations={streamState.citations} onClose={() => setDrawerOpen(false)} onOpenVideo={openVideo} open={drawerOpen} selectedVideo={selectedVideo} {...(selectedVideoUrl ? { videoUrl: selectedVideoUrl } : {})} />
    </div>
  );
}
