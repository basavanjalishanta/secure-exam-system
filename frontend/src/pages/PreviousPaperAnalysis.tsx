import { useState } from "react";
import api from "../services/api";
import { Alert, Bar, PageHeader } from "../components/ui";
import SubjectPicker from "../components/SubjectPicker";
import { useWorkflow } from "../context/WorkflowContext";

export default function PreviousPaperAnalysis() {
  const { subjectId } = useWorkflow();
  const [analysis, setAnalysis] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function analyze() {
    setBusy(true);
    setErr("");
    try {
      const r = await api.post("/pattern/analyze", { subject_id: subjectId });
      setAnalysis(r.data.analysis);
    } catch (e: any) {
      setErr(e.response?.data?.error || "Analysis failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Previous Paper Analysis"
        subtitle="Extracts question counts, marks, unit distribution, repeats and section structure"
        actions={
          <button className="btn-primary" disabled={!subjectId || busy} onClick={analyze}>
            {busy ? "Analyzing…" : "Analyze Previous Papers"}
          </button>
        }
      />
      <SubjectPicker />
      {err && <Alert kind="error">{err}</Alert>}

      {analysis && (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="card">
            <h3 className="mb-1 font-medium">Overview</h3>
            <p className="text-sm text-slate-600">
              {analysis.papers_analyzed} papers · {analysis.questions_found} questions ·{" "}
              {analysis.repeated_question_count} repeated
            </p>
          </div>
          <div className="card">
            <h3 className="mb-3 font-medium">Unit Distribution (%)</h3>
            <Bar data={analysis.unit_distribution_percent || {}} />
          </div>
          <div className="card">
            <h3 className="mb-3 font-medium">Marks Distribution</h3>
            <Bar data={analysis.marks_distribution || {}} />
          </div>
          <div className="card">
            <h3 className="mb-3 font-medium">Question Types</h3>
            <Bar data={analysis.question_type_distribution || {}} />
          </div>
          <div className="card">
            <h3 className="mb-3 font-medium">Difficulty</h3>
            <Bar data={analysis.difficulty_distribution || {}} />
          </div>
          <div className="card">
            <h3 className="mb-2 font-medium">Section Structure</h3>
            <ul className="text-sm text-slate-600">
              {(analysis.section_structure || []).map((s: any) => (
                <li key={s.section}>
                  Section {s.section}: {s.count} × {s.marks_each} = {s.total}
                </li>
              ))}
            </ul>
          </div>
          <div className="card lg:col-span-2">
            <h3 className="mb-2 font-medium">Frequently Asked Topics</h3>
            <div className="flex flex-wrap gap-2">
              {(analysis.frequently_asked_topics || []).map((t: string) => (
                <span key={t} className="badge bg-slate-100 text-slate-700">
                  {t}
                </span>
              ))}
            </div>
          </div>
          <div className="card lg:col-span-2">
            <h3 className="mb-2 font-medium">Repeated Questions</h3>
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
              {(analysis.repeated_questions || []).map((q: string, i: number) => (
                <li key={i}>{q}</li>
              ))}
              {(!analysis.repeated_questions || analysis.repeated_questions.length === 0) && (
                <li className="list-none text-slate-400">None detected.</li>
              )}
            </ul>
          </div>
          <div className="card lg:col-span-2">
            <h3 className="mb-2 font-medium">Suggested Pattern</h3>
            <pre className="overflow-x-auto rounded bg-slate-50 p-3 text-xs">
              {JSON.stringify(analysis.suggested_pattern, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
