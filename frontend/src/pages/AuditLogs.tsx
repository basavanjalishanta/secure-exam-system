import { useEffect, useState } from "react";
import api from "../services/api";
import { PageHeader, Spinner } from "../components/ui";

export default function AuditLogs() {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState("");

  function load() {
    setLoading(true);
    api.get("/audit-logs", { params: action ? { action } : {} }).then((r) => {
      setLogs(r.data.logs);
      setLoading(false);
    });
  }
  useEffect(load, []);

  return (
    <div>
      <PageHeader title="Audit Logs" subtitle="Every security-relevant action is recorded" />
      <div className="mb-4 flex gap-2">
        <input
          className="input max-w-xs"
          placeholder="Filter by action (e.g. GENERATE_PAPER)"
          value={action}
          onChange={(e) => setAction(e.target.value)}
        />
        <button className="btn-ghost" onClick={load}>
          Filter
        </button>
      </div>
      {loading ? (
        <Spinner />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2">Time</th>
                <th className="px-3 py-2">User</th>
                <th className="px-3 py-2">Action</th>
                <th className="px-3 py-2">Details</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((l) => (
                <tr key={l.id} className="border-t border-slate-100 align-top">
                  <td className="px-3 py-2 whitespace-nowrap text-slate-400">
                    {new Date(l.timestamp).toLocaleString()}
                  </td>
                  <td className="px-3 py-2">{l.user_email || "—"}</td>
                  <td className="px-3 py-2 font-medium">{l.action}</td>
                  <td className="px-3 py-2 text-xs text-slate-500">
                    {Object.entries(l)
                      .filter(([k]) => !["id", "timestamp", "user_email", "action", "user_id", "ip", "path"].includes(k))
                      .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
                      .join("  ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
