import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../services/api";
import { PageHeader, Spinner, StatCard, Bar } from "../components/ui";

export default function AdminDashboard() {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    api.get("/dashboard/stats").then((r) => setData(r.data));
  }, []);
  if (!data) return <Spinner label="Loading…" />;
  const s = data.stats;

  return (
    <div>
      <PageHeader title="Admin Dashboard" subtitle="System-wide overview and management" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Subjects" value={s.total_subjects} />
        <StatCard title="Question Bank" value={s.total_questions} />
        <StatCard title="Papers (all users)" value={s.generated_papers} />
        <StatCard title="Documents" value={s.uploaded_documents} />
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <div className="card">
          <h3 className="mb-3 font-medium">Question Distribution by Unit</h3>
          <Bar data={data.unit_coverage} />
        </div>
        <div className="card">
          <h3 className="mb-3 font-medium">System Activity (latest)</h3>
          <ul className="space-y-1 text-sm">
            {data.recent_activity.map((a: any) => (
              <li key={a.id} className="flex justify-between">
                <span>
                  <span className="font-medium">{a.action}</span>{" "}
                  <span className="text-slate-400">{a.user_email}</span>
                </span>
                <span className="text-xs text-slate-400">
                  {new Date(a.timestamp).toLocaleTimeString()}
                </span>
              </li>
            ))}
          </ul>
          <Link to="/audit" className="mt-3 inline-block text-sm text-brand-600 hover:underline">
            View full audit log →
          </Link>
        </div>
      </div>
      <div className="mt-6 flex gap-3">
        <Link to="/users" className="btn-primary">Manage Users</Link>
        <Link to="/subjects" className="btn-ghost">Manage Subjects</Link>
        <Link to="/question-bank" className="btn-ghost">Question Bank</Link>
      </div>
    </div>
  );
}
