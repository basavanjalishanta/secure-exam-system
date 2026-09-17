import { ReactNode } from "react";

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-slate-500">
      <div className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-brand-600" />
      {label && <span className="text-sm">{label}</span>}
    </div>
  );
}

export function StatCard({ title, value, hint }: { title: string; value: ReactNode; hint?: string }) {
  return (
    <div className="card">
      <p className="text-sm text-slate-500">{title}</p>
      <p className="mt-1 text-3xl font-semibold text-slate-900">{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Alert({ kind = "info", children }: { kind?: "info" | "error" | "success"; children: ReactNode }) {
  const styles = {
    info: "bg-blue-50 text-blue-800 border-blue-200",
    error: "bg-red-50 text-red-800 border-red-200",
    success: "bg-green-50 text-green-800 border-green-200",
  }[kind];
  return <div className={`rounded-lg border px-4 py-3 text-sm ${styles}`}>{children}</div>;
}

export function Bar({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data);
  const max = Math.max(1, ...entries.map(([, v]) => v));
  return (
    <div className="space-y-2">
      {entries.length === 0 && <p className="text-sm text-slate-400">No data yet.</p>}
      {entries.map(([k, v]) => (
        <div key={k} className="flex items-center gap-3">
          <span className="w-28 shrink-0 truncate text-xs text-slate-500">{k}</span>
          <div className="h-3 flex-1 rounded bg-slate-100">
            <div className="h-3 rounded bg-brand-500" style={{ width: `${(v / max) * 100}%` }} />
          </div>
          <span className="w-8 text-right text-xs text-slate-600">{v}</span>
        </div>
      ))}
    </div>
  );
}
