import { useEffect, useState } from "react";
import api from "../services/api";
import { Bar, PageHeader, Spinner, StatCard } from "../components/ui";
import { useAuth } from "../hooks/useAuth";

export default function Dashboard() {
  const { user } = useAuth();
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api
      .get("/dashboard/stats")
      .then((r) => setData(r.data))
      .catch((e) => setErr(e.response?.data?.error || "Failed to load"));
  }, []);

  if (err) return <p className="text-sm text-red-600">{err}</p>;
  if (!data) return <Spinner label="Loading dashboard…" />;

  const s = data.stats;
  return (
    <div>
      <PageHeader title={`Welcome, ${user?.name}`} subtitle={`Signed in as ${user?.role}`} />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Total Subjects" value={s.total_subjects} />
        <StatCard title="Total Questions" value={s.total_questions} hint="question bank" />
        <StatCard title="Generated Papers" value={s.generated_papers} />
        <StatCard title="Uploaded Documents" value={s.uploaded_documents} />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <div className="card">
          <h3 className="mb-3 font-medium">Unit Coverage</h3>
          <Bar data={data.unit_coverage} />
        </div>
        <div className="card">
          <h3 className="mb-3 font-medium">Difficulty Distribution</h3>
          <Bar data={data.difficulty_distribution} />
        </div>
        <div className="card">
          <h3 className="mb-3 font-medium">Question Types</h3>
          <Bar data={data.question_type_distribution} />
        </div>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <div className="card">
          <h3 className="mb-3 font-medium">Recent Activity</h3>
          <ul className="space-y-2 text-sm">
            {data.recent_activity.map((a: any) => (
              <li key={a.id} className="flex justify-between border-b border-slate-100 pb-1">
                <span className="text-slate-700">{a.action}</span>
                <span className="text-xs text-slate-400">
                  {new Date(a.timestamp).toLocaleString()}
                </span>
              </li>
            ))}
            {data.recent_activity.length === 0 && <li className="text-slate-400">No activity yet.</li>}
          </ul>
        </div>
        <div className="card">
          <h3 className="mb-3 font-medium">Generation History</h3>
          <ul className="space-y-2 text-sm">
            {data.generation_history.map((g: any) => (
              <li key={g.id} className="flex justify-between border-b border-slate-100 pb-1">
                <span className="text-slate-700">Generation {g.generation_id?.slice(0, 8)}</span>
                <span className="text-xs text-slate-400">
                  {new Date(g.created_at).toLocaleString()}
                </span>
              </li>
            ))}
            {data.generation_history.length === 0 && (
              <li className="text-slate-400">No generations yet.</li>
            )}
          </ul>
        </div>
      </div>
    </div>
  );
}
