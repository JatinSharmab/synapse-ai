export const DEFAULT_READINESS_DELAYS_MS = [0, 4_000, 8_000, 12_000, 16_000, 20_000] as const;

export interface ReadinessPollingOptions {
  delaysMs?: readonly number[];
  onWaiting?: (failedAttempt: number) => void;
  signal?: AbortSignal;
}

function abortError(): Error {
  return new Error("Readiness polling was cancelled.");
}

async function wait(delayMs: number, signal?: AbortSignal): Promise<void> {
  if (signal?.aborted) throw abortError();
  if (delayMs <= 0) return;
  await new Promise<void>((resolve, reject) => {
    const cleanup = () => signal?.removeEventListener("abort", abort);
    const timeout = globalThis.setTimeout(() => {
      cleanup();
      resolve();
    }, delayMs);
    const abort = () => {
      globalThis.clearTimeout(timeout);
      cleanup();
      reject(abortError());
    };
    signal?.addEventListener("abort", abort, { once: true });
  });
}

export async function pollReadiness<T>(
  probe: () => Promise<T>,
  options: ReadinessPollingOptions = {},
): Promise<T> {
  const delays = options.delaysMs ?? DEFAULT_READINESS_DELAYS_MS;
  if (delays.length === 0) throw new Error("At least one readiness attempt is required.");

  let lastError: unknown;
  for (let index = 0; index < delays.length; index += 1) {
    await wait(delays[index] ?? 0, options.signal);
    if (options.signal?.aborted) throw abortError();
    try {
      return await probe();
    } catch (error) {
      lastError = error;
      options.onWaiting?.(index + 1);
    }
  }
  throw lastError instanceof Error ? lastError : new Error("Synapse AI is not ready.");
}
