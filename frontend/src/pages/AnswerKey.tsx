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

  async function generate() {
    setBusy(true);
    setErr("");
    try {
      const r = await api.post("/answers/generate", { subject_id: subjectId, questions });
      setQuestions(r.data.questions);
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
        <Alert kind="info">Generate questions first.</Alert>
      </div>
    );

  const withAnswers = questions.filter((q) => q.answer).length;

  return (
    <div>
      <PageHeader
        title="Answer Key"
        subtitle={`${withAnswers}/${questions.length} answered — depth scales with marks, sourced from textbook/notes`}
        actions={
          <div className="flex gap-2">
            <button className="btn-primary" disabled={busy} onClick={generate}>
              {busy ? "Generating…" : "Generate Answers"}
            </button>
            <button className="btn-ghost" onClick={() => navigate("/paper")}>
              Create Paper
            </button>
          </div>
        }
      />
      {err && <Alert kind="error">{err}</Alert>}
      {busy && <Spinner label="Retrieving context and drafting answers…" />}

      <div className="space-y-4">
        {questions.map((q, i) => (
          <div key={i} className="card">
            <p className="font-medium">
              Q{i + 1}. ({q.marks}) {q.question}
            </p>
            {q.answer ? (
              <>
                <pre className="mt-2 whitespace-pre-wrap rounded bg-slate-50 p-3 text-sm text-slate-700">
                  {q.answer}
                </pre>
                <p className="mt-1 text-xs text-slate-400">
                  Support score: {q.answer_support ?? "—"} · Sources:{" "}
                  {(q as any).answer_sources?.join(", ")}
                </p>
              </>
            ) : (
              <p className="mt-2 text-sm text-slate-400">Not generated yet.</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
