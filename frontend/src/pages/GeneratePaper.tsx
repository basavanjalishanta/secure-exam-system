import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";
import { Alert, PageHeader, Spinner } from "../components/ui";
import { useWorkflow } from "../context/WorkflowContext";

export default function GeneratePaper() {
  const navigate = useNavigate();
  const { subjectId, pattern, questions } = useWorkflow();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState("");
  const [meta, setMeta] = useState({
    college_name: "University College of Engineering",
    exam_name: "End Semester Examination",
    date: new Date().toISOString().slice(0, 10),
    time: "3 Hours",
    instructions: "Answer ALL questions.\nFigures to the right indicate full marks.",
  });

  async function create() {
    setBusy(true);
    setErr("");
    try {
      const r = await api.post("/papers/generate", {
        subject_id: subjectId,
        pattern,
        questions,
        meta: {
          ...meta,
          instructions: meta.instructions.split("\n").filter(Boolean),
        },
      });
      setResult(r.data.paper);
    } catch (e: any) {
      setErr(e.response?.data?.error || "Paper generation failed");
    } finally {
      setBusy(false);
    }
  }

  if (questions.length === 0)
    return (
      <div>
        <PageHeader title="Generate Paper" />
        <Alert kind="info">No questions in the workflow. Generate and validate questions first.</Alert>
      </div>
    );

  return (
    <div>
      <PageHeader
        title="Generate Paper"
        subtitle="Builds a university-style PDF + answer key, then encrypts both with AES-256"
      />
      {err && <Alert kind="error">{err}</Alert>}

      {!result && (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="card space-y-3">
            <h3 className="font-medium">Paper header</h3>
            {(["college_name", "exam_name", "date", "time"] as const).map((k) => (
              <div key={k}>
                <label className="label capitalize">{k.replace("_", " ")}</label>
                <input
                  className="input"
                  value={(meta as any)[k]}
                  onChange={(e) => setMeta({ ...meta, [k]: e.target.value })}
                />
              </div>
            ))}
            <div>
              <label className="label">Instructions (one per line)</label>
              <textarea
                className="input min-h-[90px]"
                value={meta.instructions}
                onChange={(e) => setMeta({ ...meta, instructions: e.target.value })}
              />
            </div>
            <button className="btn-primary w-full" disabled={busy} onClick={create}>
              {busy ? "Building & encrypting…" : "Create Paper (PDF + AES-256)"}
            </button>
            {busy && <Spinner label="ReportLab → AES-256-GCM → MongoDB" />}
          </div>

          <div className="card">
            <h3 className="mb-2 font-medium">Preview ({questions.length} questions)</h3>
            <ol className="space-y-1 text-sm">
              {questions.map((q, i) => (
                <li key={i}>
                  <span className="text-slate-400">{q.section}{i + 1}.</span> {q.question}{" "}
                  <span className="text-xs text-slate-400">[{q.marks}]</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}

      {result && (
        <div className="card max-w-lg space-y-3">
          <Alert kind="success">Paper created and encrypted.</Alert>
          <dl className="text-sm">
            <Row k="Paper ID" v={result.id} />
            <Row k="Subject" v={result.subject_name} />
            <Row k="Total marks" v={result.total_marks} />
            <Row k="Questions banked" v={result.questions_added_to_bank} />
            <Row k="Encryption" v={`${result.encryption.paper.algorithm} · plaintext not stored`} />
          </dl>
          <div className="flex gap-2">
            <button className="btn-primary" onClick={() => navigate(`/papers/${result.id}`)}>
              Secure Download
            </button>
            <button className="btn-ghost" onClick={() => navigate("/papers")}>
              All Papers
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ k, v }: { k: string; v: any }) {
  return (
    <div className="flex justify-between border-b border-slate-100 py-1">
      <dt className="text-slate-500">{k}</dt>
      <dd className="font-medium">{String(v)}</dd>
    </div>
  );
}
