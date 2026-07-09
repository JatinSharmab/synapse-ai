export interface SeekableMedia {
  currentTime: number;
}

export function seekVideo(media: SeekableMedia, startSeconds: number): void {
  if (Number.isFinite(startSeconds) && startSeconds >= 0) media.currentTime = startSeconds;
}
