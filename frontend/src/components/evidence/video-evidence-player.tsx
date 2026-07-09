import { Film, Play } from "lucide-react";
import { useEffect, useRef } from "react";

import { seekVideo } from "@/components/evidence/video-utils";

export interface VideoEvidenceSelection {
  description?: string;
  endSeconds: number;
  filename: string;
  segmentId: string;
  startSeconds: number;
  videoId: string;
}

function timestamp(seconds: number): string {
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60).toString().padStart(2, "0")}:${(whole % 60).toString().padStart(2, "0")}`;
}

export function VideoEvidencePlayer({ evidence, sourceUrl }: { evidence: VideoEvidenceSelection; sourceUrl?: string }) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (videoRef.current?.readyState) seekVideo(videoRef.current, evidence.startSeconds);
  }, [evidence, sourceUrl]);

  return (
    <section className="overflow-hidden rounded-2xl border border-white/[0.08] bg-black/30" aria-label="Video evidence player">
      {sourceUrl ? (
        <video
          className="aspect-video w-full bg-black object-contain"
          controls
          onLoadedMetadata={(event) => seekVideo(event.currentTarget, evidence.startSeconds)}
          preload="metadata"
          ref={videoRef}
          src={sourceUrl}
        >
          Your browser does not support video playback.
        </video>
      ) : (
        <div className="grid aspect-video place-items-center bg-slate-950/80 px-6 text-center">
          <div>
            <Film className="mx-auto h-7 w-7 text-slate-600" aria-hidden="true" />
            <p className="mt-3 text-xs leading-5 text-slate-500">The trusted timestamp is available, but this local session does not hold the video binary.</p>
          </div>
        </div>
      )}
      <div className="p-4">
        <div className="flex items-center justify-between gap-3">
          <p className="truncate text-sm font-medium text-slate-200">{evidence.filename}</p>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-violet-300/15 bg-violet-300/[0.06] px-2.5 py-1 font-mono text-[10px] text-violet-200">
            <Play className="h-3 w-3" aria-hidden="true" /> {timestamp(evidence.startSeconds)}–{timestamp(evidence.endSeconds)}
          </span>
        </div>
        {evidence.description ? <p className="mt-3 text-xs leading-5 text-slate-400">{evidence.description}</p> : null}
      </div>
    </section>
  );
}
