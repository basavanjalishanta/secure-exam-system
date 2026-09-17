import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { Subject } from "../services/api";
import { Alert, PageHeader, Spinner } from "../components/ui";
import SubjectPicker from "../components/SubjectPicker";
import { useWorkflow } from "../context/WorkflowContext";

const DIFFICULTIES = ["", "Easy", "Medium", "Hard"];
const BLOOMS = ["", "Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"];

export default function QuestionGeneration() {
  const navigate = useNavigate();
  const { subjectId, pattern, setPattern, setQuestions, setValidation } = useWorkflow();
  const [subject, setSubject] = useState<Subject | null>(null);
  const [units, setUnits] = useState<number[]>([]);
  const [difficulty, setDifficulty] = useState("");
  const [bloom, setBloom] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [provider, setProvider] = useState("");

  const totalQuestions = pattern?.sections.reduce((a, s) => a + s.count, 0) ?? 0;

  function onSubject(s: Subject | null) {
    setSubject(s);
    if (s) {
      setUnits(s.units.map((u) => u.unit));
      if (s.selected_pattern) setPattern(s.selected_pattern);
    }
  }

  useEffect(() => {
    api.get("/health").then((r) => setProvider(r.data.ai_provider)).catch(() => {});
  }, []);

  function toggleUnit(u: number) {
    setUnits((prev) => (prev.includes(u) ? prev.filter((x) => x !== u) : [...prev, u]));
  }

  async function generate() {
    if (!subjectId || !pattern) return;
    setBusy(true);
    setErr("");
    setValidation(null);
    try {
      const r = await api.post("/questions/generate", {
        subject_id: subjectId,
        pattern,
        units,
        difficulty: difficulty || undefined,
        bloom_level: bloom || undefined,
      });
      setQuestions(r.data.questions);
      navigate("/review");
    } catch (e: any) {
      setErr(e.response?.data?.error || "Generation failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="AI Question Generation"
        subtitle="Retrieval-Augmented generation — questions come only from your uploaded material"
      />
      <SubjectPicker onChange={onSubject} />

      {!subjectId && <Alert kind="info">Select a subject.</Alert>}
      {subjectId && !pattern && (
        <Alert kind="error">No pattern selected. Go to Pattern Selection first.</Alert>
      )}

      {subject && pattern && (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="card space-y-4 lg:col-span-2">
            <div>
              <p className="label">Marks pattern</p>
              <p className="text-sm text-slate-600">
                {pattern.name} — {totalQuestions} questions, {pattern.total_marks} marks
              </p>
              <div className="mt-1 flex flex-wrap gap-2">
                {pattern.sections.map((s) => (
                  <span key={s.section} className="badge bg-slate-100 text-slate-700">
                    {s.section}: {s.count}×{s.marks_each}
                  </span>
                ))}
              </div>
            </div>

            <div>
              <p className="label">Units to include</p>
              <div className="flex flex-wrap gap-2">
                {subject.units.map((u) => (
                  <button
                    key={u.unit}
                    onClick={() => toggleUnit(u.unit)}
                    className={`badge border px-3 py-1 ${
                      units.includes(u.unit)
                        ? "border-brand-500 bg-brand-50 text-brand-700"
                        : "border-slate-200 text-slate-500"
                    }`}
                  >
                    Unit {u.unit} {u.title && `– ${u.title}`}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Difficulty override</label>
                <select className="input" value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
                  {DIFFICULTIES.map((d) => (
                    <option key={d} value={d}>
                      {d || "Auto (from marks)"}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Bloom level override</label>
                <select className="input" value={bloom} onChange={(e) => setBloom(e.target.value)}>
                  {BLOOMS.map((b) => (
                    <option key={b} value={b}>
                      {b || "Auto (from marks)"}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex flex-wrap gap-3 pt-2">
              <button className="btn-ghost" onClick={() => navigate("/analysis")}>
                Analyze Pattern
              </button>
              <button className="btn-primary" onClick={generate} disabled={busy || units.length === 0}>
                {busy ? "Generating…" : "Generate Questions"}
              </button>
            </div>
            {busy && <Spinner label="Running RAG + LLM + duplicate detection…" />}
            {err && <Alert kind="error">{err}</Alert>}
          </div>

          <div className="card">
            <h3 className="mb-2 font-medium">AI Provider</h3>
            <p className="text-sm text-slate-600">
              Active: <span className="badge bg-brand-50 text-brand-700">{provider || "…"}</span>
            </p>
            <p className="mt-2 text-xs text-slate-400">
              Set <code>AI_PROVIDER=llama</code> and <code>LLAMA_BASE_URL</code> in the backend{" "}
              <code>.env</code> to use a local LLaMA-compatible model. The <code>mock</code> provider
              composes questions from retrieved context for offline testing.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
