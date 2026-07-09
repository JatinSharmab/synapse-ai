import {
  Database,
  FileText,
  Film,
  FolderOpen,
  RefreshCw,
  UploadCloud,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from "react";

import { listKnowledge, uploadKnowledge, type UploadKind } from "@/api/client";
import type { KnowledgeSource } from "@/api/schemas";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

type SourceFilter = "all" | UploadKind;

interface KnowledgeLibraryProps {
  aiServiceUrl: string;
  gatewayUrl: string;
  directUploadsEnabled: boolean;
  onVideoAvailable: (videoId: string, filename: string, sourceUrl: string) => void;
}

const sourcePresentation = {
  document: { accept: ".pdf,application/pdf", description: "Page-aware grounded retrieval", icon: FileText, label: "PDF" },
  video: { accept: ".mp4,video/mp4", description: "Timestamped multimodal evidence", icon: Film, label: "Video" },
  dataset: { accept: ".csv,text/csv", description: "Constrained deterministic analysis", icon: Database, label: "CSV" },
} as const;

function sourceName(source: KnowledgeSource): string {
  return source.record.filename;
}

function sourceMeta(source: KnowledgeSource): string {
  if (source.kind === "document") {
    return source.record.ocr_required
      ? "OCR required · not indexed"
      : `${source.record.page_count} pages · ${source.record.chunk_count} chunks`;
  }
  if (source.kind === "video") {
    return `${Math.round(source.record.duration_seconds)} sec · ${source.record.segment_count} segments · ${source.record.processing_status}`;
  }
  return `${source.record.row_count.toLocaleString()} rows · ${source.record.columns.length} columns`;
}

export function KnowledgeLibrary({ aiServiceUrl, gatewayUrl, directUploadsEnabled, onVideoAvailable }: KnowledgeLibraryProps) {
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<SourceFilter>("all");
  const [uploading, setUploading] = useState<UploadKind | null>(null);
  const [notice, setNotice] = useState<{ kind: "error" | "success"; text: string } | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const result = await listKnowledge(aiServiceUrl);
      setSources(result.sources);
      setWarnings(result.warnings);
    } finally {
      setLoading(false);
    }
  }, [aiServiceUrl]);

  useEffect(() => {
    let active = true;
    void listKnowledge(aiServiceUrl).then((result) => {
      if (!active) return;
      setSources(result.sources);
      setWarnings(result.warnings);
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [aiServiceUrl]);

  const visibleSources = useMemo(
    () => sources.filter((source) => filter === "all" || source.kind === filter),
    [filter, sources],
  );

  const onFile = async (kind: UploadKind, event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || (!directUploadsEnabled && kind === "dataset")) return;
    setUploading(kind);
    setNotice(null);
    try {
      const uploaded = await uploadKnowledge(aiServiceUrl, gatewayUrl, kind, file, directUploadsEnabled);
      setSources((current) => [uploaded, ...current.filter((source) => source.id !== uploaded.id)]);
      if (kind === "video" && uploaded.kind === "video") {
        const sourceUrl = URL.createObjectURL(file);
        onVideoAvailable(uploaded.record.video_id, uploaded.record.filename, sourceUrl);
      }
      setNotice({ kind: "success", text: `${file.name} is ready in the knowledge library.` });
    } catch (error) {
      setNotice({
        kind: "error",
        text: error instanceof Error ? error.message : "The source could not be uploaded.",
      });
    } finally {
      setUploading(null);
    }
  };

  return (
    <section className="mx-auto w-full max-w-6xl px-4 pb-24 pt-5 sm:px-6 lg:px-8 lg:pb-10 lg:pt-8" aria-labelledby="knowledge-title">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="eyebrow">Grounded intelligence</p>
          <h1 id="knowledge-title" className="mt-2 text-2xl font-semibold tracking-[-0.025em] text-white sm:text-3xl">Knowledge Library</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">Curate the trusted PDFs, videos, and datasets Synapse can retrieve and analyze.</p>
        </div>
        <Button onClick={() => void refresh()} variant="secondary">
          <RefreshCw className="h-4 w-4" aria-hidden="true" /> Refresh library
        </Button>
      </div>

      <div className="mt-7 grid gap-3 md:grid-cols-3">
        {(Object.entries(sourcePresentation) as [UploadKind, (typeof sourcePresentation)[UploadKind]][]).map(([kind, item]) => {
          const Icon = item.icon;
          return (
            <Panel className="group relative overflow-hidden p-5" key={kind}>
              <div className="flex items-start justify-between gap-4">
                <span className="grid h-10 w-10 place-items-center rounded-xl border border-white/[0.08] bg-white/[0.04] text-slate-300">
                  <Icon className="h-4.5 w-4.5" aria-hidden="true" />
                </span>
                <span className="rounded-full border border-white/[0.08] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">{item.label}</span>
              </div>
              <h2 className="mt-5 text-sm font-medium text-white">Add {item.label} source</h2>
              <p className="mt-1.5 text-xs leading-5 text-slate-500">{item.description}</p>
              <label className={cn("mt-5 inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-xl border border-white/10 bg-white/[0.045] px-4 text-xs font-medium text-slate-200 transition hover:border-cyan-300/30 hover:text-white", ((!directUploadsEnabled && kind === "dataset") || uploading !== null) && "pointer-events-none opacity-45")}>
                <UploadCloud className="h-3.5 w-3.5" aria-hidden="true" />
                {uploading === kind ? "Processing…" : "Choose file"}
                <input accept={item.accept} className="sr-only" disabled={(!directUploadsEnabled && kind === "dataset") || uploading !== null} onChange={(event) => void onFile(kind, event)} type="file" />
              </label>
            </Panel>
          );
        })}
      </div>

      {!directUploadsEnabled ? (
        <p className="mt-4 rounded-xl border border-amber-300/15 bg-amber-300/[0.06] px-4 py-3 text-xs leading-5 text-amber-100/80">
          PDFs and videos upload directly from this browser to private object storage. CSV upload remains local-development only.
        </p>
      ) : null}
      {notice ? (
        <p className={cn("mt-4 rounded-xl border px-4 py-3 text-xs", notice.kind === "success" ? "border-emerald-300/15 bg-emerald-300/[0.06] text-emerald-200" : "border-rose-300/15 bg-rose-300/[0.06] text-rose-200")} role="status">
          {notice.text}
        </p>
      ) : null}

      <div className="mt-9 flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.07] pb-4">
        <div className="flex gap-1 rounded-xl border border-white/[0.07] bg-slate-950/50 p-1">
          {(["all", "document", "video", "dataset"] as const).map((item) => (
            <button className={cn("rounded-lg px-3 py-2 text-xs capitalize text-slate-500 transition", filter === item && "bg-white/[0.07] text-slate-100")} key={item} onClick={() => setFilter(item)} type="button">
              {item === "all" ? "All sources" : sourcePresentation[item].label}
            </button>
          ))}
        </div>
        <p className="text-xs text-slate-500">{visibleSources.length} trusted source{visibleSources.length === 1 ? "" : "s"}</p>
      </div>

      {warnings.length ? <p className="mt-4 text-xs text-amber-200/70">{warnings.join(" · ")}</p> : null}
      {loading ? (
        <div className="mt-5 space-y-3" aria-label="Loading knowledge library">
          {[0, 1, 2].map((item) => <Skeleton className="h-20 w-full" key={item} />)}
        </div>
      ) : visibleSources.length ? (
        <ul className="mt-3 divide-y divide-white/[0.06]">
          {visibleSources.map((source) => {
            const presentation = sourcePresentation[source.kind];
            const Icon = presentation.icon;
            return (
              <li className="flex items-center gap-4 py-4" key={source.id}>
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white/[0.04] text-slate-400"><Icon className="h-4 w-4" aria-hidden="true" /></span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-slate-200">{sourceName(source)}</p>
                  <p className="mt-1 truncate text-xs capitalize text-slate-500">{sourceMeta(source)}</p>
                </div>
                <span className="hidden rounded-full border border-emerald-300/15 bg-emerald-300/[0.05] px-2.5 py-1 text-[10px] uppercase tracking-wider text-emerald-300 sm:block">Indexed</span>
              </li>
            );
          })}
        </ul>
      ) : (
        <div className="mt-8 rounded-2xl border border-dashed border-white/10 py-14 text-center">
          <FolderOpen className="mx-auto h-6 w-6 text-slate-600" aria-hidden="true" />
          <p className="mt-4 text-sm font-medium text-slate-300">No trusted sources yet</p>
          <p className="mx-auto mt-2 max-w-sm text-xs leading-5 text-slate-500">Upload a PDF, short MP4, or CSV to give Synapse grounded context.</p>
        </div>
      )}
    </section>
  );
}
