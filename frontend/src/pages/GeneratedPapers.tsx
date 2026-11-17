import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../services/api";
import { PageHeader, Spinner } from "../components/ui";

export default function GeneratedPapers() {
  const [papers, setPapers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/papers").then((r) => {
      setPapers(r.data.papers);
      setLoading(false);
    });
  }, []);

  if (loading) return <Spinner label="Loading papers…" />;

  return (
    <div>
      <PageHeader title="Generated Papers" subtitle="Encrypted at rest · access controlled" />
      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Subject</th>
              <th className="px-4 py-3">Marks</th>
              <th className="px-4 py-3">Questions</th>
              <th className="px-4 py-3">Created by</th>
              <th className="px-4 py-3">Created</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {papers.map((p) => (
              <tr key={p.id} className="border-t border-slate-100">
                <td className="px-4 py-3 font-medium">{p.subject_name}</td>
                <td className="px-4 py-3">{p.total_marks}</td>
                <td className="px-4 py-3">{p.question_count}</td>
                <td className="px-4 py-3">{p.created_by_name}</td>
                <td className="px-4 py-3 text-slate-400">
                  {new Date(p.created_at).toLocaleDateString()}
                </td>
                <td className="px-4 py-3">
                  <span className="badge bg-green-100 text-green-700">Encrypted ✓</span>
                </td>
                <td className="px-4 py-3">
                  <Link to={`/papers/${p.id}`} className="text-brand-600 hover:underline">
                    Open
                  </Link>
                </td>
              </tr>
            ))}
            {papers.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-slate-400">
                  No papers generated yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
