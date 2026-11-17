import { FormEvent, useEffect, useState } from "react";
import api, { Subject } from "../services/api";
import { Alert, PageHeader, Spinner } from "../components/ui";
import { useWorkflow } from "../context/WorkflowContext";

export default function SubjectManagement() {
  const { subjectId, setSubjectId } = useWorkflow();
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState({ name: "", code: "", semester: 1, unitCount: 5 });
  const [units, setUnits] = useState<{ unit: number; title: string }[]>(
    Array.from({ length: 5 }, (_, i) => ({ unit: i + 1, title: "" })),
  );

  function load() {
    api.get("/subjects").then((r) => {
      setSubjects(r.data.subjects);
      setLoading(false);
    });
  }
  useEffect(load, []);

  function setUnitCount(n: number) {
    setForm({ ...form, unitCount: n });
    setUnits(Array.from({ length: n }, (_, i) => units[i] || { unit: i + 1, title: "" }));
  }

  async function create(e: FormEvent) {
    e.preventDefault();
    setMsg("");
    try {
      await api.post("/subjects", {
        name: form.name,
        code: form.code,
        semester: Number(form.semester),
        units,
      });
      setForm({ name: "", code: "", semester: 1, unitCount: 5 });
      load();
      setMsg("Subject created.");
    } catch (err: any) {
      setMsg(err.response?.data?.error || "Failed");
    }
  }

  if (loading) return <Spinner label="Loading subjects…" />;

  return (
    <div>
      <PageHeader title="Subject Management" subtitle="Create subjects and select the one you are working on" />
      {msg && <div className="mb-4"><Alert kind="info">{msg}</Alert></div>}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="card">
          <h3 className="mb-3 font-medium">Subjects</h3>
          <div className="space-y-2">
            {subjects.map((s) => (
              <label
                key={s.id}
                className={`flex cursor-pointer items-center justify-between rounded-lg border p-3 ${
                  subjectId === s.id ? "border-brand-500 bg-brand-50" : "border-slate-200"
                }`}
              >
                <div>
                  <p className="font-medium">
                    {s.name} <span className="text-slate-400">({s.code})</span>
                  </p>
                  <p className="text-xs text-slate-500">
                    Sem {s.semester} · {s.units.length} units
                    {s.selected_pattern && ` · pattern: ${s.selected_pattern.name}`}
                  </p>
                </div>
                <input
                  type="radio"
                  name="subject"
                  checked={subjectId === s.id}
                  onChange={() => setSubjectId(s.id)}
                />
              </label>
            ))}
            {subjects.length === 0 && <p className="text-sm text-slate-400">No subjects yet.</p>}
          </div>
        </div>

        <form onSubmit={create} className="card space-y-3">
          <h3 className="font-medium">New Subject</h3>
          <div>
            <label className="label">Name</label>
            <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Code</label>
              <input className="input" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required />
            </div>
            <div>
              <label className="label">Semester</label>
              <input
                className="input"
                type="number"
                min={1}
                max={10}
                value={form.semester}
                onChange={(e) => setForm({ ...form, semester: Number(e.target.value) })}
              />
            </div>
          </div>
          <div>
            <label className="label">Number of units</label>
            <input
              className="input"
              type="number"
              min={1}
              max={10}
              value={form.unitCount}
              onChange={(e) => setUnitCount(Number(e.target.value))}
            />
          </div>
          {units.map((u, i) => (
            <input
              key={u.unit}
              className="input"
              placeholder={`Unit ${u.unit} title`}
              value={u.title}
              onChange={(e) => {
                const next = [...units];
                next[i] = { ...u, title: e.target.value };
                setUnits(next);
              }}
            />
          ))}
          <button className="btn-primary w-full">Create subject</button>
        </form>
      </div>
    </div>
  );
}
