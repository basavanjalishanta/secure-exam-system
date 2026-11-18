import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { Question } from "../services/api";
import { Alert, PageHeader } from "../components/ui";
import { useWorkflow } from "../context/WorkflowContext";

export default function QuestionReview() {
  const navigate = useNavigate();
  const { subjectId, questions, setQuestions } = useWorkflow();
  const [editing, setEditing] = useState<number | null>(null);

  useEffect(() => {
    if (questions.length === 0) {
      api
        .get(`/questions/latest${subjectId ? `?subject_id=${subjectId}` : ""}`)
        .then((r) => {
          if (r.data.questions && r.data.questions.length > 0) {
            setQuestions(r.data.questions);
          }
        })
        .catch(() => {});
    }
  }, [subjectId, questions.length]);

  const [busyIdx, setBusyIdx] = useState<number | null>(null);
  const [msg, setMsg] = useState("");

  function update(i: number, patch: Partial<Question>) {
    setQuestions(questions.map((q, idx) => (idx === i ? { ...q, ...patch } : q)));
  }
  function remove(i: number) {
    setQuestions(questions.filter((_, idx) => idx !== i));
  }

  async function regenerate(i: number) {
    setBusyIdx(i);
    setMsg("");
    try {
      const r = await api.post("/questions/regenerate", {
        subject_id: subjectId,
        question: questions[i],
        existing_questions: questions.map((q) => q.question),
      });
      update(i, r.data.question);
    } catch (e: any) {
      setMsg(e.response?.data?.error || "Regeneration failed");
    } finally {
      setBusyIdx(null);
    }
  }

  const total = questions.reduce(
    (a, q) => a + (q.is_or ? 0 : Number(q.marks || 0)),
    0,
  );

  if (questions.length === 0)
    return (
      <div>
        <PageHeader title="Question Review" />
        <Alert kind="info">No generated questions. Run AI Question Generation first.</Alert>
      </div>
    );

  return (
    <div>
      <PageHeader
        title="Question Review"
        subtitle={`${questions.length} questions \u00b7 ${total} marks \u2013 edit, regenerate or delete`}
        actions={
          <div className="flex gap-2">
            <button className="btn-ghost" onClick={() => navigate("/answers")}>
              Generate Answers
            </button>
            <button className="btn-primary" onClick={() => navigate("/validation")}>
              Validate
            </button>
          </div>
        }
      />
      {msg && <Alert kind="error">{msg}</Alert>}

      <div className="space-y-4">
        {questions.map((q, i) => (
          <div key={i} className={`card ${q.duplicate ? "border-amber-300 bg-amber-50" : ""}`}>
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                {editing === i ? (
                  <textarea
                    className="input min-h-[80px]"
                    value={q.question}
                    onChange={(e) => update(i, { question: e.target.value })}
                  />
                ) : (
                  <p className="font-medium">
                    <span className="text-slate-400">Q{i + 1} ({q.section}).</span> {q.question}
                  </p>
                )}
                <div className="mt-2 flex flex-wrap gap-2 text-xs">
                  <Meta label="Unit" value={q.unit} onEdit={editing === i ? (v) => update(i, { unit: Number(v) }) : undefined} />
                  <Meta label="Topic" value={q.topic} onEdit={editing === i ? (v) => update(i, { topic: v }) : undefined} />
                  <Meta label="Marks" value={q.marks} onEdit={editing === i ? (v) => update(i, { marks: Number(v) }) : undefined} />
                  <Meta label="Difficulty" value={q.difficulty} onEdit={editing === i ? (v) => update(i, { difficulty: v }) : undefined} />
                  <Meta label="Bloom" value={q.bloom_level} onEdit={editing === i ? (v) => update(i, { bloom_level: v }) : undefined} />
                  <span className="badge bg-slate-100 text-slate-600">{q.question_type}</span>
                  {q.bl && <span className="badge bg-purple-50 text-purple-700">BL: {q.bl}</span>}
                  {q.co && <span className="badge bg-blue-50 text-blue-700">CO: {q.co}</span>}
                  {q.po && <span className="badge bg-green-50 text-green-700">PO: {q.po}</span>}
                  {q.pso && <span className="badge bg-orange-50 text-orange-700">PSO: {q.pso}</span>}
                  <span
                    className={`badge ${
                      q.duplicate
                        ? "bg-amber-100 text-amber-700"
                        : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    sim {q.similarity_score?.toFixed(2) ?? "-"}
                  </span>
                </div>
                {q.source && q.source.length > 0 && (
                  <p className="mt-2 text-xs text-slate-400">Source: {q.source.join("; ")}</p>
                )}
                {q.duplicate && (
                  <p className="mt-1 text-xs text-amber-700">
                    &#9888; Near-duplicate of: {q.matched_question}
                  </p>
                )}
              </div>
            </div>
            <div className="mt-3 flex gap-2">
              <button
                className="btn-ghost !py-1 !text-xs"
                onClick={() => setEditing(editing === i ? null : i)}
              >
                {editing === i ? "Done" : "Edit"}
              </button>
              <button
                className="btn-ghost !py-1 !text-xs"
                disabled={busyIdx === i}
                onClick={() => regenerate(i)}
              >
                {busyIdx === i ? "Regenerating..." : "Regenerate"}
              </button>
              <button className="btn-danger !py-1 !text-xs" onClick={() => remove(i)}>
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Meta({
  label,
  value,
  onEdit,
}: {
  label: string;
  value: any;
  onEdit?: (v: string) => void;
}) {
  if (onEdit)
    return (
      <span className="inline-flex items-center gap-1 rounded bg-slate-100 px-1.5 py-0.5">
        {label}:
        <input
          className="w-20 rounded border border-slate-300 px-1 text-xs"
          value={value}
          onChange={(e) => onEdit(e.target.value)}
        />
      </span>
    );
  return (
    <span className="badge bg-slate-100 text-slate-600">
      {label}: {value}
    </span>
  );
}
