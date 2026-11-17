import { useEffect, useState } from "react";
import api, { Pattern } from "../services/api";
import { Alert, PageHeader } from "../components/ui";
import SubjectPicker from "../components/SubjectPicker";
import { useWorkflow } from "../context/WorkflowContext";

export default function PatternSelection() {
  const { subjectId, pattern, setPattern } = useWorkflow();
  const [defaults, setDefaults] = useState<Pattern[]>([]);
  const [suggested, setSuggested] = useState<Pattern | null>(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api.get("/pattern/defaults").then((r) => setDefaults(r.data.patterns));
  }, []);

  useEffect(() => {
    if (!subjectId) return;
    api.get(`/subjects/${subjectId}`).then((r) => {
      const a = r.data.subject.pattern_analysis;
      setSuggested(a?.suggested_pattern || null);
      if (r.data.subject.selected_pattern) setPattern(r.data.subject.selected_pattern);
    });
  }, [subjectId]);

  async function choose(mode: "auto" | "manual", p?: Pattern) {
    const r = await api.post("/pattern/select", { subject_id: subjectId, mode, pattern: p });
    setPattern(r.data.pattern);
    setMsg(`Selected "${r.data.pattern.name}" (${mode}).`);
  }

  const options = [
    ...(suggested ? [{ ...suggested, name: suggested.name + " (auto from previous papers)" }] : []),
    ...defaults,
  ];

  return (
    <div>
      <PageHeader title="Pattern Selection" subtitle="Auto-select from analysis, or pick a pattern manually" />
      <SubjectPicker />
      {!subjectId && <Alert kind="info">Select a subject first.</Alert>}
      {msg && <div className="mb-4"><Alert kind="success">{msg}</Alert></div>}

      {subjectId && (
        <>
          <div className="mb-4 flex gap-3">
            <button className="btn-primary" onClick={() => choose("auto")}>
              Auto-select pattern
            </button>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {options.map((p, i) => (
              <div
                key={i}
                className={`card ${pattern?.name === p.name ? "ring-2 ring-brand-500" : ""}`}
              >
                <div className="flex items-center justify-between">
                  <h3 className="font-medium">{p.name}</h3>
                  <span className="badge bg-brand-50 text-brand-700">{p.total_marks} marks</span>
                </div>
                <table className="mt-3 w-full text-sm">
                  <tbody>
                    {p.sub_parts && (
                      <tr className="border-b border-slate-100 font-medium text-brand-600">
                        <td className="py-1">Sub-parts per Q:</td>
                        <td className="py-1 text-right">{p.sub_parts.join(" + ")} marks (with OR choice)</td>
                      </tr>
                    )}
                    {(p.sections || []).map((s) => (
                      <tr key={s.section} className="border-b border-slate-100">
                        <td className="py-1">{s.section.startsWith("Unit") ? s.section : `Section ${s.section}`}</td>
                        <td className="py-1 text-right">
                          {s.count} × {s.marks_each} = {s.total}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <button className="btn-ghost mt-3 w-full" onClick={() => choose("manual", p)}>
                  Use this pattern
                </button>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
