import { CheckCircle2, CloudCog, RefreshCw, ServerCrash } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { getSystemReadiness } from "@/api/client";
import type { ProviderInfo } from "@/api/schemas";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

type Readiness = "checking" | "ready" | "warming" | "unavailable";

interface SystemStatusProps {
  aiServiceUrl: string;
  gatewayUrl: string;
}

export function SystemStatus({ aiServiceUrl, gatewayUrl }: SystemStatusProps) {
  const [status, setStatus] = useState<Readiness>("checking");
  const [provider, setProvider] = useState<ProviderInfo | null>(null);

  const check = useCallback(async () => {
    setStatus("checking");
    setProvider(null);
    const warmingTimer = window.setTimeout(() => setStatus("warming"), 1_800);
    try {
      const readiness = await getSystemReadiness(gatewayUrl, aiServiceUrl, {
        onWaiting: () => setStatus("warming"),
      });
      setProvider(readiness.provider);
      setStatus("ready");
    } catch {
      setStatus("unavailable");
    } finally {
      window.clearTimeout(warmingTimer);
    }
  }, [aiServiceUrl, gatewayUrl]);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const warmingTimer = window.setTimeout(() => {
      if (active) setStatus("warming");
    }, 1_800);
    void getSystemReadiness(gatewayUrl, aiServiceUrl, {
      onWaiting: () => {
        if (active) setStatus("warming");
      },
      signal: controller.signal,
    })
      .then((readiness) => {
        if (!active) return;
        setProvider(readiness.provider);
        setStatus("ready");
      })
      .catch(() => {
        if (active) setStatus("unavailable");
      })
      .finally(() => window.clearTimeout(warmingTimer));
    return () => {
      active = false;
      controller.abort();
      window.clearTimeout(warmingTimer);
    };
  }, [aiServiceUrl, gatewayUrl]);

  if (status === "checking") {
    return (
      <div className="space-y-3" aria-label="Checking system readiness">
        <Skeleton className="h-5 w-28" />
        <Skeleton className="h-3 w-full" />
      </div>
    );
  }

  const ready = status === "ready";
  const warming = status === "warming";
  const Icon = ready ? CheckCircle2 : warming ? CloudCog : ServerCrash;
  return (
    <section aria-label="System readiness" className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className={ready ? "text-emerald-300" : warming ? "text-amber-300" : "text-rose-300"}>
            <Icon className="h-4 w-4" aria-hidden="true" />
          </span>
          <div>
            <p className="text-sm font-medium text-slate-100">
              {ready ? "Systems ready" : warming ? "Waking Synapse AI service..." : "Services unavailable"}
            </p>
            <p className="mt-0.5 text-xs text-slate-500">
              {ready && provider ? `${provider.mock ? "Mock" : "Mistral"} provider · ${provider.models.chat}` : "Gateway + intelligence service"}
            </p>
          </div>
        </div>
        {!ready ? (
          <Button aria-label="Retry readiness check" className="h-8 min-h-8 w-8 px-0" onClick={() => void check()} variant="ghost">
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
          </Button>
        ) : null}
      </div>
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <span className="rounded-lg bg-white/[0.035] px-2.5 py-2 text-slate-400">Transport {ready ? "online" : "pending"}</span>
        <span className="rounded-lg bg-white/[0.035] px-2.5 py-2 text-slate-400">AI core {ready ? "online" : "pending"}</span>
      </div>
    </section>
  );
}
