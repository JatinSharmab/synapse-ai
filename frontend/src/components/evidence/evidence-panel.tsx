import { ExternalLink, FileText, Film, Quote } from "lucide-react";

import type { StreamEvent } from "../../../../shared/streaming.js";
import type { VideoEvidenceSelection } from "@/components/evidence/video-evidence-player";

type Citation = Extract<StreamEvent, { type: "response.completed" }>["citations"][number];

interface EvidencePanelProps {
  citations: Citation[];
  onOpenVideo: (selection: VideoEvidenceSelection) => void;
}

export function EvidencePanel({ citations, onOpenVideo }: EvidencePanelProps) {
  return (
    <section aria-label="Sources and evidence">
      <div>
        <h2 className="text-sm font-semibold text-slate-100">Sources & Evidence</h2>
        <p className="mt-1 text-xs text-slate-500">Trusted retrieval provenance</p>
      </div>
      {citations.length === 0 ? (
        <div className="mt-5 rounded-xl border border-dashed border-white/10 px-4 py-6 text-center">
          <Quote className="mx-auto h-5 w-5 text-slate-600" aria-hidden="true" />
          <p className="mt-3 text-xs leading-5 text-slate-500">Grounded sources will appear with exact pages or timestamps.</p>
        </div>
      ) : (
        <ol className="mt-4 space-y-2.5">
          {citations.map((citation, index) => {
            const video = citation.source_type === "video";
            const Icon = video ? Film : FileText;
            return (
              <li key={citation.citation_id}>
                <button
                  className="group flex w-full items-start gap-3 rounded-xl border border-white/[0.07] bg-white/[0.025] p-3 text-left transition hover:border-cyan-300/20 hover:bg-white/[0.045]"
                  onClick={() => {
                    if (citation.source_type === "video") {
                      onOpenVideo({
                        endSeconds: citation.end_seconds,
                        filename: citation.filename,
                        segmentId: citation.segment_id,
                        startSeconds: citation.start_seconds,
                        videoId: citation.video_id,
                      });
                    }
                  }}
                  type="button"
                >
                  <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-white/[0.05] text-slate-400"><Icon className="h-3.5 w-3.5" aria-hidden="true" /></span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-xs font-medium text-slate-200">{index + 1}. {citation.filename}</span>
                    <span className="mt-1 block truncate text-[11px] text-slate-500">{citation.locator}</span>
                  </span>
                  {video ? <ExternalLink className="mt-1 h-3 w-3 text-slate-600 transition group-hover:text-cyan-300" aria-hidden="true" /> : null}
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
