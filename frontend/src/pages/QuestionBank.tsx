import { useEffect, useState } from "react";
import api from "../services/api";
import { PageHeader, Spinner } from "../components/ui";
import SubjectPicker from "../components/SubjectPicker";
import { useWorkflow } from "../context/WorkflowContext";

export default function QuestionBank() {
  const { subjectId } = useWorkflow();
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ unit: "", difficulty: "", search: "" });

  function load() {
    setLoading(true);
    const params: any = {};
    if (subjectId) params.subject_id = subjectId;
    if (filters.unit) params.unit = filters.unit;
    if (filters.difficulty) params.difficulty = filters.difficulty;
    if (filters.search) params.search = filters.search;
    api.get("/question-bank", { params }).then((r) => {
      setRows(r.data.questions);
      setLoading(false);
    });
  }
  useEffect(load, [subjectId]);

  async function del(id: string) {
    await api.delete(`/question-bank/${id}`);
    load();
  }

  return (
    <div>
      <PageHeader title="Question Bank" subtitle="Every validated question, stored with embeddings for duplicate detection" />
      <SubjectPicker />
      <div className="mb-4 flex flex-wrap gap-2">
        <input
          className="input max-w-[160px]"
          placeholder="Unit"
          value={filters.unit}
          onChange={(e) => setFilters({ ...filters, unit: e.target.value })}
        />
        <select
          className="input max-w-[160px]"
          value={filters.difficulty}
          onChange={(e) => setFilters({ ...filters, difficulty: e.target.value })}
        >
          <option value="">Any difficulty</option>
          {["Easy", "Medium", "Hard"].map((d) => (
            <option key={d}>{d}</option>
          ))}
        </select>
        <input
          className="input max-w-[220px]"
          placeholder="Search text"
          value={filters.search}
          onChange={(e) => setFilters({ ...filters, search: e.target.value })}
        />
        <button className="btn-ghost" onClick={load}>
          Apply
        </button>
      </div>

      {loading ? (
        <Spinner />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2">Question</th>
                <th className="px-3 py-2">Unit</th>
                <th className="px-3 py-2">Marks</th>
                <th className="px-3 py-2">Difficulty</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Used</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((q) => (
                <tr key={q.id} className="border-t border-slate-100 align-top">
                  <td className="px-3 py-2">{q.question}</td>
                  <td className="px-3 py-2">{q.unit}</td>
                  <td className="px-3 py-2">{q.marks}</td>
                  <td className="px-3 py-2">{q.difficulty}</td>
                  <td className="px-3 py-2">{q.question_type}</td>
                  <td className="px-3 py-2">{q.usage_count}</td>
                  <td className="px-3 py-2">
                    <button className="text-xs text-red-600 hover:underline" onClick={() => del(q.id)}>
                      delete
                    </button>
                  </td>
                </tr>
              ))}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-3 py-6 text-center text-slate-400">
                    No questions in the bank yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
