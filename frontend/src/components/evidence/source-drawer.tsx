import { X } from "lucide-react";
import { useEffect } from "react";

import type { StreamEvent } from "../../../../shared/streaming.js";
import { EvidencePanel } from "@/components/evidence/evidence-panel";
import { VideoEvidencePlayer, type VideoEvidenceSelection } from "@/components/evidence/video-evidence-player";
import { Button } from "@/components/ui/button";

interface SourceDrawerProps {
  citations: Extract<StreamEvent, { type: "response.completed" }>["citations"];
  onClose: () => void;
  onOpenVideo: (selection: VideoEvidenceSelection) => void;
  open: boolean;
  selectedVideo: VideoEvidenceSelection | null;
  videoUrl?: string;
}

export function SourceDrawer({ citations, onClose, onOpenVideo, open, selectedVideo, videoUrl }: SourceDrawerProps) {
  useEffect(() => {
    if (!open) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose, open]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="Source evidence drawer">
      <button aria-label="Close source drawer" className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm" onClick={onClose} type="button" />
      <aside className="absolute inset-y-0 right-0 w-full max-w-md overflow-y-auto border-l border-white/10 bg-[#080d18] p-5 shadow-2xl animate-slide-in sm:p-6">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <p className="eyebrow">Evidence layer</p>
            <h2 className="mt-1 text-lg font-semibold text-white">Source detail</h2>
          </div>
          <Button aria-label="Close drawer" className="h-9 min-h-9 w-9 px-0" onClick={onClose} variant="ghost"><X className="h-4 w-4" /></Button>
        </div>
        {selectedVideo ? <div className="mb-6"><VideoEvidencePlayer evidence={selectedVideo} {...(videoUrl ? { sourceUrl: videoUrl } : {})} /></div> : null}
        <EvidencePanel citations={citations} onOpenVideo={onOpenVideo} />
      </aside>
    </div>
  );
}
