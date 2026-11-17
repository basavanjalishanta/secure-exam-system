import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";
import { Alert, PageHeader, Spinner } from "../components/ui";
import { useWorkflow } from "../context/WorkflowContext";

export default function AnswerKey() {
  const navigate = useNavigate();
  const { subjectId, questions, setQuestions } = useWorkflow();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [progress, setProgress] = useState({ done: 0, total: 0 });

  async function generate() {
    setBusy(true);
    setErr("");
    setProgress({ done: 0, total: questions.length });
    try {
      const r = await api.post("/answers/generate", { subject_id: subjectId, questions });
      setQuestions(r.data.questions);
      setProgress({ done: r.data.questions.filter((q: any) => q.answer).length, total: r.data.questions.length });
    } catch (e: any) {
      setErr(e.response?.data?.error || "Answer generation failed");
    } finally {
      setBusy(false);
    }
  }

  if (questions.length === 0)
    return (
      <div>
        <PageHeader title="Answer Key" />
        <Alert kind="info">Generate questions first then come back here.</Alert>
      </div>
    );

  const withAnswers = questions.filter((q) => q.answer).length;

  return (
    <div>
      <PageHeader
        title="Answer Key"
        subtitle={`${withAnswers}/${questions.length} answered \u2013 depth scales with marks, sourced from textbook/notes`}
        actions={
          <div className="flex gap-2">
            <button className="btn-primary" disabled={busy} onClick={generate}>
              {busy ? "Generating..." : "Generate Answers"}
            </button>
            <button className="btn-ghost" onClick={() => navigate("/paper")}>
              Create Paper
            </button>
          </div>
        }
      />
      {err && <Alert kind="error">{err}</Alert>}

      {busy && (
        <div className="mb-4 space-y-2">
          <Spinner label="Retrieving context and drafting answers..." />
          <p className="text-xs text-slate-500">
            Note: Using Groq free tier &mdash; each answer takes ~5-8 seconds. Total time for{" "}
            {questions.length} questions: ~{Math.ceil(questions.length * 7 / 60)} minutes.
          </p>
        </div>
      )}

      <div className="space-y-4">
        {questions.map((q, i) => (
          <div key={i} className="card">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-700">
                {i + 1}
              </span>
              <div className="flex-1">
                <p className="font-medium text-slate-800">
                  <span className="mr-2 badge bg-slate-100 text-slate-600">{q.marks} marks</span>
                  {q.question}
                </p>
                <div className="mt-1 flex flex-wrap gap-1 text-xs">
                  <span className="badge bg-blue-50 text-blue-700">Unit {q.unit}</span>
                  <span className="badge bg-slate-50 text-slate-600">{q.bloom_level}</span>
                  <span className="badge bg-slate-50 text-slate-600">{q.difficulty}</span>
                </div>
                {q.answer ? (
                  <>
                    <pre className="mt-3 whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-sm text-slate-700 border border-slate-200">
                      {q.answer}
                    </pre>
                    <p className="mt-1 text-xs text-slate-400">
                      Support score: {q.answer_support ?? "-"} &middot; Sources:{" "}
                      {(q as any).answer_sources?.join(", ") || "textbook/syllabus"}
                    </p>
                  </>
                ) : (
                  <p className="mt-2 text-sm text-slate-400 italic">
                    {busy ? "Generating..." : "Not generated yet. Click 'Generate Answers' above."}
                  </p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
