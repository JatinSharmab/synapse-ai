import type { ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowUpRight, Film } from "lucide-react";

import { genUIComponentSchema, type GenUIComponent, type GenUIType } from "./schema.js";

export type VideoEvidenceItem = Extract<GenUIComponent, { type: "video_evidence" }>["items"][number];

interface RendererProps {
  component: GenUIComponent;
  onVideoEvidence?: (item: VideoEvidenceItem) => void;
}

type RegistryRenderer = (props: RendererProps) => ReactNode;

const palette = ["#67e8f9", "#a78bfa", "#34d399", "#fbbf24", "#fb7185", "#60a5fa"];
const tooltipStyle = {
  background: "#0b1220",
  border: "1px solid rgba(255,255,255,.1)",
  borderRadius: "10px",
  color: "#e2e8f0",
  fontSize: "12px",
};

function displayValue(value: unknown): string {
  return value === null || value === undefined ? "—" : String(value);
}

function ChartFrame({ children, title }: { children: ReactNode; title: string }) {
  return (
    <figure aria-label={title} className="genui-card min-w-0">
      <figcaption className="mb-5 text-sm font-medium text-slate-100">{title}</figcaption>
      <div className="h-64 w-full min-w-0">{children}</div>
    </figure>
  );
}

const TextRenderer: RegistryRenderer = ({ component }) =>
  component.type === "text" ? (
    <article className="genui-card">
      {component.title ? <h3 className="mb-2 text-sm font-medium text-white">{component.title}</h3> : null}
      <p className="text-sm leading-7 text-slate-300">{component.text}</p>
    </article>
  ) : null;

const MetricRenderer: RegistryRenderer = ({ component }) =>
  component.type === "metric" ? (
    <article className="genui-card relative overflow-hidden">
      <span className="absolute inset-y-0 left-0 w-0.5 bg-cyan-300" aria-hidden="true" />
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">{component.label}</p>
      <p className="mt-3 text-3xl font-semibold tracking-[-0.035em] text-white">
        {component.value}
        {component.unit ? <span className="ml-1.5 text-sm font-normal text-slate-500">{component.unit}</span> : null}
      </p>
    </article>
  ) : null;

const BarChartRenderer: RegistryRenderer = ({ component }) =>
  component.type === "bar_chart" ? (
    <ChartFrame title={component.title}>
      <ResponsiveContainer height="100%" width="100%">
        <BarChart data={component.data} margin={{ bottom: 0, left: -18, right: 4, top: 4 }}>
          <CartesianGrid stroke="rgba(148,163,184,.10)" strokeDasharray="3 5" vertical={false} />
          <XAxis axisLine={false} dataKey={component.config.xKey} fontSize={11} stroke="#64748b" tickLine={false} />
          <YAxis axisLine={false} fontSize={11} stroke="#64748b" tickLine={false} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(103,232,249,.04)" }} />
          <Bar dataKey={component.config.yKey} fill="#67e8f9" radius={[5, 5, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  ) : null;

const LineChartRenderer: RegistryRenderer = ({ component }) =>
  component.type === "line_chart" ? (
    <ChartFrame title={component.title}>
      <ResponsiveContainer height="100%" width="100%">
        <LineChart data={component.data} margin={{ bottom: 0, left: -18, right: 8, top: 4 }}>
          <CartesianGrid stroke="rgba(148,163,184,.10)" strokeDasharray="3 5" vertical={false} />
          <XAxis axisLine={false} dataKey={component.config.xKey} fontSize={11} stroke="#64748b" tickLine={false} />
          <YAxis axisLine={false} fontSize={11} stroke="#64748b" tickLine={false} />
          <Tooltip contentStyle={tooltipStyle} />
          <Line activeDot={{ r: 4 }} dataKey={component.config.yKey} dot={false} stroke="#67e8f9" strokeWidth={2} type="monotone" />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  ) : null;

const PieChartRenderer: RegistryRenderer = ({ component }) =>
  component.type === "pie_chart" ? (
    <ChartFrame title={component.title}>
      <div className="grid h-full grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
        <ResponsiveContainer height="100%" width="100%">
          <PieChart>
            <Pie cx="50%" cy="50%" data={component.data} dataKey={component.config.valueKey} innerRadius="56%" nameKey={component.config.labelKey} outerRadius="82%" paddingAngle={2} stroke="transparent">
              {component.data.map((row, index) => <Cell fill={palette[index % palette.length]} key={`${displayValue(row[component.config.labelKey])}-${index}`} />)}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} />
          </PieChart>
        </ResponsiveContainer>
        <ul className="max-w-36 space-y-2 pr-2 text-[11px] text-slate-400">
          {component.data.slice(0, 6).map((row, index) => (
            <li className="flex items-center gap-2" key={`${displayValue(row[component.config.labelKey])}-legend-${index}`}>
              <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ backgroundColor: palette[index % palette.length] }} />
              <span className="truncate">{displayValue(row[component.config.labelKey])}</span>
            </li>
          ))}
        </ul>
      </div>
    </ChartFrame>
  ) : null;

const TableRenderer: RegistryRenderer = ({ component }) =>
  component.type === "table" ? (
    <div className="genui-card overflow-hidden p-0">
      <p className="border-b border-white/[0.07] px-5 py-4 text-sm font-medium text-white">{component.title}</p>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-xs">
          <thead className="bg-white/[0.025]"><tr>{component.columns.map((column) => <th className="whitespace-nowrap px-5 py-3 font-medium text-slate-500" key={column.key}>{column.label}</th>)}</tr></thead>
          <tbody>{component.data.map((row, index) => <tr className="border-t border-white/[0.05]" key={index}>{component.columns.map((column) => <td className="whitespace-nowrap px-5 py-3 text-slate-300" key={column.key}>{displayValue(row[column.key])}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </div>
  ) : null;

const CitationListRenderer: RegistryRenderer = ({ component }) =>
  component.type === "citation_list" ? (
    <section className="genui-card">
      <h3 className="text-sm font-medium text-white">{component.title}</h3>
      <ol className="mt-3 divide-y divide-white/[0.06]">
        {component.citations.map((citation, index) => <li className="flex items-start gap-3 py-3 first:pt-1 last:pb-0" key={citation.citation_id}><span className="font-mono text-[10px] text-cyan-300">{String(index + 1).padStart(2, "0")}</span><span className="min-w-0"><span className="block truncate text-xs text-slate-300">{citation.label}</span><span className="mt-1 block text-[11px] text-slate-500">{citation.locator}</span></span></li>)}
      </ol>
    </section>
  ) : null;

const VideoEvidenceRenderer: RegistryRenderer = ({ component, onVideoEvidence }) =>
  component.type === "video_evidence" ? (
    <section className="genui-card">
      <h3 className="text-sm font-medium text-white">{component.title}</h3>
      <ul className="mt-4 grid gap-3 sm:grid-cols-2">
        {component.items.map((item) => <li key={item.segment_id}><button className="group w-full rounded-xl border border-white/[0.07] bg-slate-950/40 p-4 text-left transition hover:border-violet-300/25" onClick={() => onVideoEvidence?.(item)} type="button"><span className="flex items-center justify-between gap-3"><Film className="h-4 w-4 text-violet-300" /><ArrowUpRight className="h-3.5 w-3.5 text-slate-600 transition group-hover:text-violet-200" /></span><span className="mt-4 block truncate text-xs font-medium text-slate-200">{item.filename}</span><span className="mt-1.5 block font-mono text-[10px] text-violet-300">{item.start_seconds.toFixed(1)}s–{item.end_seconds.toFixed(1)}s</span><span className="mt-2 line-clamp-2 block text-[11px] leading-5 text-slate-500">{item.description}</span></button></li>)}
      </ul>
    </section>
  ) : null;

// Fixed, statically imported renderers are the only executable UI surface.
// eslint-disable-next-line react-refresh/only-export-components
export const componentRegistry: Readonly<Record<GenUIType, RegistryRenderer>> = Object.freeze({
  text: TextRenderer,
  metric: MetricRenderer,
  bar_chart: BarChartRenderer,
  line_chart: LineChartRenderer,
  pie_chart: PieChartRenderer,
  table: TableRenderer,
  citation_list: CitationListRenderer,
  video_evidence: VideoEvidenceRenderer,
});

export function SafeTextFallback({ text }: { text: string }) {
  return <p data-testid="genui-fallback" className="genui-card text-sm leading-6 text-slate-300">{text}</p>;
}

export function GenUIRenderer({ fallbackText, onVideoEvidence, payload }: { fallbackText: string; onVideoEvidence?: (item: VideoEvidenceItem) => void; payload: unknown }) {
  const parsed = genUIComponentSchema.safeParse(payload);
  if (!parsed.success) return <SafeTextFallback text={fallbackText} />;
  const Renderer = componentRegistry[parsed.data.type];
  return <Renderer component={parsed.data} {...(onVideoEvidence ? { onVideoEvidence } : {})} />;
}
