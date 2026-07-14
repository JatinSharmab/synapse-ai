export interface RateLimitResult {
  allowed: boolean;
  limit: number;
  remaining: number;
  resetAt: number;
}

interface RateLimitEntry {
  count: number;
  resetAt: number;
}

export class FixedWindowRateLimiter {
  private readonly entries = new Map<string, RateLimitEntry>();

  public constructor(
    private readonly limit: number,
    private readonly windowMs: number,
    private readonly now: () => number = Date.now,
  ) {}

  public consume(key: string): RateLimitResult {
    const now = this.now();
    const current = this.entries.get(key);
    const entry =
      current === undefined || current.resetAt <= now
        ? { count: 0, resetAt: now + this.windowMs }
        : current;
    entry.count += 1;
    this.entries.set(key, entry);
    if (this.entries.size > 10_000) {
      this.removeExpired(now);
    }
    return {
      allowed: entry.count <= this.limit,
      limit: this.limit,
      remaining: Math.max(0, this.limit - entry.count),
      resetAt: entry.resetAt,
    };
  }

  private removeExpired(now: number): void {
    for (const [key, entry] of this.entries) {
      if (entry.resetAt <= now) {
        this.entries.delete(key);
      }
    }
  }
}
