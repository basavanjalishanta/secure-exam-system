import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
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
  if (!data) return <Spinner label="Loading dashboard..." />;

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

      {/* Quick Workflow Action Shortcuts */}
      <div className="mt-6 rounded-xl border border-blue-200 bg-blue-50/50 p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-blue-900">Lecturer Examination Workflow</h3>
        <p className="mt-0.5 text-xs text-blue-700">Automated end-to-end question paper lifecycle:</p>
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-6">
          <Link
            to="/upload"
            className="flex flex-col items-center justify-center rounded-lg border border-slate-200 bg-white p-3 text-center shadow-sm hover:border-blue-500 hover:shadow"
          >
            <span className="text-xs font-bold text-blue-600">Step 1</span>
            <span className="mt-1 text-xs font-medium text-slate-800">Upload Syllabus</span>
          </Link>
          <Link
            to="/lesson-plan"
            className="flex flex-col items-center justify-center rounded-lg border border-blue-300 bg-white p-3 text-center shadow-sm ring-2 ring-blue-400 hover:border-blue-600 hover:shadow"
          >
            <span className="text-xs font-bold text-blue-600">Step 2</span>
            <span className="mt-1 text-xs font-semibold text-blue-900">Lesson Plan</span>
          </Link>
          <Link
            to="/pattern"
            className="flex flex-col items-center justify-center rounded-lg border border-slate-200 bg-white p-3 text-center shadow-sm hover:border-blue-500 hover:shadow"
          >
            <span className="text-xs font-bold text-blue-600">Step 3</span>
            <span className="mt-1 text-xs font-medium text-slate-800">Exam Pattern</span>
          </Link>
          <Link
            to="/generate"
            className="flex flex-col items-center justify-center rounded-lg border border-slate-200 bg-white p-3 text-center shadow-sm hover:border-blue-500 hover:shadow"
          >
            <span className="text-xs font-bold text-blue-600">Step 4</span>
            <span className="mt-1 text-xs font-medium text-slate-800">AI Generation</span>
          </Link>
          <Link
            to="/review"
            className="flex flex-col items-center justify-center rounded-lg border border-slate-200 bg-white p-3 text-center shadow-sm hover:border-blue-500 hover:shadow"
          >
            <span className="text-xs font-bold text-blue-600">Step 5</span>
            <span className="mt-1 text-xs font-medium text-slate-800">Review &amp; Edit</span>
          </Link>
          <Link
            to="/paper"
            className="flex flex-col items-center justify-center rounded-lg border border-slate-200 bg-white p-3 text-center shadow-sm hover:border-blue-500 hover:shadow"
          >
            <span className="text-xs font-bold text-blue-600">Step 6</span>
            <span className="mt-1 text-xs font-medium text-slate-800">Export &amp; Encrypt</span>
          </Link>
        </div>
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
            {data.recent_activity.length === 0 && (
              <li className="text-slate-400">No activity yet.</li>
            )}
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
