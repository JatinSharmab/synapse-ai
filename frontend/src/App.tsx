import type { LucideIcon } from "lucide-react";
import { Activity, Blocks, BrainCircuit, Network, ShieldCheck, Terminal } from "lucide-react";

import { StatusBadge } from "@/components/ui/status-badge";
import { runtimeConfig } from "@/config";

interface FoundationCard {
  description: string;
  icon: LucideIcon;
  label: string;
  value: string;
}

const foundationCards: FoundationCard[] = [
  {
    label: "Experience layer",
    value: "React workspace ready",
    description: "Typed Vite and Tailwind foundation with a fixed component boundary.",
    icon: Blocks,
  },
  {
    label: "API boundary",
    value: "Gateway health online",
    description: "Thin Express service prepared for validation and safe proxying.",
    icon: Network,
  },
  {
    label: "Intelligence core",
    value: "FastAPI health online",
    description: "Python service boundary ready for future, explicitly scoped AI phases.",
    icon: BrainCircuit,
  },
];

export function App() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="pointer-events-none fixed inset-0 overflow-hidden" aria-hidden="true">
        <div className="absolute left-1/2 top-[-22rem] h-[42rem] w-[42rem] -translate-x-1/2 rounded-full bg-cyan-400/10 blur-3xl" />
        <div className="absolute bottom-[-20rem] right-[-8rem] h-[36rem] w-[36rem] rounded-full bg-violet-500/10 blur-3xl" />
      </div>

      <header className="relative border-b border-white/10 bg-slate-950/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl border border-cyan-300/20 bg-cyan-300/10 text-cyan-200">
              <BrainCircuit className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-sm font-semibold tracking-[0.28em] text-white">SYNAPSE</p>
              <p className="text-xs text-slate-400">Enterprise AI Intelligence OS</p>
            </div>
          </div>
          <StatusBadge>Phase 1 foundation</StatusBadge>
        </div>
      </header>

      <main className="relative mx-auto max-w-7xl px-6 py-16 lg:px-8 lg:py-24">
        <section className="max-w-4xl">
          <div className="mb-6 flex items-center gap-2 text-sm font-medium text-cyan-200">
            <Activity className="h-4 w-4" aria-hidden="true" />
            Development environment initialized
          </div>
          <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-white sm:text-6xl">
            A disciplined foundation for multimodal AI engineering.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
            This shell confirms the service boundaries and developer experience for Synapse. AI
            workflows, retrieval, providers, and the final workspace remain intentionally deferred.
          </p>
        </section>

        <section className="mt-14 grid gap-4 md:grid-cols-3" aria-label="Foundation services">
          {foundationCards.map(({ description, icon: Icon, label, value }) => (
            <article
              key={label}
              className="rounded-2xl border border-white/10 bg-slate-900/70 p-6 shadow-panel backdrop-blur"
            >
              <div className="flex items-center justify-between">
                <Icon className="h-5 w-5 text-cyan-300" aria-hidden="true" />
                <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_16px_rgba(52,211,153,0.9)]" />
              </div>
              <p className="mt-8 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                {label}
              </p>
              <h2 className="mt-2 text-lg font-medium text-white">{value}</h2>
              <p className="mt-3 text-sm leading-6 text-slate-400">{description}</p>
            </article>
          ))}
        </section>

        <section className="mt-6 grid gap-4 lg:grid-cols-[1.4fr_1fr]">
          <article className="rounded-2xl border border-white/10 bg-slate-900/50 p-6">
            <div className="flex items-center gap-3">
              <ShieldCheck className="h-5 w-5 text-violet-300" aria-hidden="true" />
              <h2 className="font-medium text-white">Phase boundary</h2>
            </div>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-400">
              No authentication, databases, agents, model providers, retrieval pipelines, or
              generated UI are active in this phase. Each capability will arrive behind a typed,
              tested contract in a separately approved phase.
            </p>
          </article>

          <article className="rounded-2xl border border-white/10 bg-slate-950/80 p-6 font-mono text-sm">
            <div className="flex items-center gap-3 text-slate-300">
              <Terminal className="h-4 w-4 text-cyan-300" aria-hidden="true" />
              <span>Gateway target</span>
            </div>
            <code className="mt-4 block overflow-x-auto text-cyan-200">
              {runtimeConfig.gatewayUrl}/health
            </code>
          </article>
        </section>
      </main>
    </div>
  );
}

