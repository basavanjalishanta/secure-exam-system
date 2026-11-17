import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { Subject } from "../services/api";
import { Alert, PageHeader, Spinner } from "../components/ui";
import SubjectPicker from "../components/SubjectPicker";
import { useWorkflow } from "../context/WorkflowContext";

const DIFFICULTIES = ["", "Easy", "Medium", "Hard"];
const BLOOMS = ["", "Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"];

interface JobProgress {
  job_id: string;
  status: "queued" | "in_progress" | "completed" | "completed_with_errors" | "failed";
  current_stage: string;
  total_slots: number;
  completed_count: number;
  failed_count: number;
  questions: any[];
  errors: string[];
}

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
  const [jobProgress, setJobProgress] = useState<JobProgress | null>(null);

  const pollIntervalRef = useRef<any>(null);

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
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  function toggleUnit(u: number) {
    setUnits((prev) => (prev.includes(u) ? prev.filter((x) => x !== u) : [...prev, u]));
  }

  function startPolling(jobId: string) {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

    pollIntervalRef.current = setInterval(async () => {
      try {
        const res = await api.get(`/questions/jobs/${jobId}`);
        const job: JobProgress = res.data.job;
        setJobProgress(job);

        if (job.status === "completed" || job.status === "completed_with_errors") {
          clearInterval(pollIntervalRef.current);
          setBusy(false);
          setQuestions(job.questions);
          // Wait 1.5 seconds so user sees 100% completion then navigate to review
          setTimeout(() => {
            navigate("/review");
          }, 1500);
        } else if (job.status === "failed") {
          clearInterval(pollIntervalRef.current);
          setBusy(false);
          setErr(job.current_stage || "Generation job failed");
        }
      } catch (pollErr: any) {
        clearInterval(pollIntervalRef.current);
        setBusy(false);
        setErr("Lost connection to generation worker.");
      }
    }, 2000);
  }

  async function generate() {
    if (!subjectId || !pattern) return;
    setBusy(true);
    setErr("");
    setValidation(null);
    setJobProgress(null);

    try {
      const r = await api.post("/questions/generate", {
        subject_id: subjectId,
        pattern,
        units,
        difficulty: difficulty || undefined,
        bloom_level: bloom || undefined,
      });

      const jobId = r.data.job_id;
      if (jobId) {
        startPolling(jobId);
      } else {
        setErr("Failed to start background job.");
        setBusy(false);
      }
    } catch (e: any) {
      setBusy(false);
      setErr(e.response?.data?.error || "Generation request failed");
    }
  }

  const percent =
    jobProgress && jobProgress.total_slots > 0
      ? Math.min(100, Math.round((jobProgress.completed_count / jobProgress.total_slots) * 100))
      : 0;

  return (
    <div>
      <PageHeader
        title="AI Question Generation"
        subtitle="Asynchronous Retrieval-Augmented Generation with live progress tracking"
      />
      <SubjectPicker onChange={onSubject} />

      {!subjectId && <Alert kind="info">Select a subject to begin.</Alert>}
      {subjectId && !pattern && (
        <Alert kind="error">No pattern selected. Go to Pattern Selection first.</Alert>
      )}

      {subject && pattern && (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="card space-y-4 lg:col-span-2">
            <div>
              <p className="label">Examination Blueprint</p>
              <p className="text-sm text-slate-600">
                {pattern.name} &mdash; {totalQuestions} questions, {pattern.total_marks} marks
              </p>
              <div className="mt-1 flex flex-wrap gap-2">
                {pattern.sections.map((s) => (
                  <span key={s.section} className="badge bg-slate-100 text-slate-700">
                    Section {s.section}: {s.count} questions &times; {s.marks_each} marks
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
                    disabled={busy}
                    className={`badge border px-3 py-1 ${
                      units.includes(u.unit)
                        ? "border-brand-500 bg-brand-50 text-brand-700"
                        : "border-slate-200 text-slate-500"
                    }`}
                  >
                    Unit {u.unit} {u.title && `\u2013 ${u.title}`}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Difficulty override</label>
                <select
                  className="input"
                  value={difficulty}
                  disabled={busy}
                  onChange={(e) => setDifficulty(e.target.value)}
                >
                  {DIFFICULTIES.map((d) => (
                    <option key={d} value={d}>
                      {d || "Auto (from marks)"}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Bloom level override</label>
                <select
                  className="input"
                  value={bloom}
                  disabled={busy}
                  onChange={(e) => setBloom(e.target.value)}
                >
                  {BLOOMS.map((b) => (
                    <option key={b} value={b}>
                      {b || "Auto (from marks)"}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex flex-wrap gap-3 pt-2">
              <button className="btn-ghost" onClick={() => navigate("/pattern")} disabled={busy}>
                Change Pattern
              </button>
              <button
                className="btn-primary"
                onClick={generate}
                disabled={busy || units.length === 0}
              >
                {busy ? "Generating Paper..." : "Generate Questions"}
              </button>
            </div>

            {/* Live Progress Card */}
            {busy && (
              <div className="mt-4 rounded-lg border border-brand-200 bg-brand-50/50 p-4 space-y-3">
                <div className="flex items-center justify-between text-sm font-medium">
                  <span className="text-brand-900 flex items-center gap-2">
                    <span className="inline-block h-2 w-2 rounded-full bg-brand-600 animate-pulse"></span>
                    {jobProgress?.current_stage || "Queued in background worker..."}
                  </span>
                  <span className="text-brand-700">{percent}%</span>
                </div>

                <div className="w-full bg-slate-200 rounded-full h-2.5 overflow-hidden">
                  <div
                    className="bg-brand-600 h-2.5 rounded-full transition-all duration-300"
                    style={{ width: `${percent}%` }}
                  ></div>
                </div>

                <div className="flex justify-between text-xs text-slate-500">
                  <span>
                    Completed: <b>{jobProgress?.completed_count ?? 0}</b> /{" "}
                    {jobProgress?.total_slots ?? totalQuestions} questions
                  </span>
                  {jobProgress && jobProgress.failed_count > 0 && (
                    <span className="text-amber-600 font-semibold">
                      Failed / Retrying: {jobProgress.failed_count}
                    </span>
                  )}
                </div>

                {/* Timing estimate */}
                {provider === "groq" && jobProgress && jobProgress.total_slots > 0 && (
                  <p className="text-xs text-slate-400">
                    Estimated time: ~{Math.ceil((jobProgress.total_slots - jobProgress.completed_count) * 17 / 60)} min remaining
                    &nbsp;(Groq free tier: 1 question every ~17s due to rate limits)
                  </p>
                )}
              </div>
            )}

            {err && (
              <div className="space-y-2">
                <Alert kind="error">{err}</Alert>
                {jobProgress && jobProgress.questions && jobProgress.questions.length > 0 && (
                  <button
                    className="btn-primary"
                    onClick={() => {
                      setQuestions(jobProgress.questions);
                      navigate("/review");
                    }}
                  >
                    Proceed to Review {jobProgress.questions.length} Generated Questions &rarr;
                  </button>
                )}
              </div>
            )}
          </div>

          <div className="card space-y-4">
            <div>
              <h3 className="mb-2 font-medium">Active AI Provider</h3>
              <p className="text-sm text-slate-600">
                Current Engine:{" "}
                <span className="badge bg-brand-50 text-brand-700 uppercase font-mono font-bold">
                  {provider || "..."}
                </span>
              </p>
              <p className="mt-2 text-xs text-slate-400">
                {provider === "groq" || provider === "grok"
                  ? "Cloud LLM (Groq free tier: ~17s/question due to 8K TPM limit)"
                  : provider === "ollama"
                  ? "Local Ollama (Offline privacy-preserving execution)"
                  : "Offline RAG deterministic composer"}
              </p>
            </div>

            <div className="border-t border-slate-100 pt-3">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Generation Pipeline
              </h4>
              <ul className="mt-2 space-y-1.5 text-xs text-slate-600">
                <li className="flex items-center gap-1.5">
                  &#10003; <b>Deterministic Blueprint:</b> Structured marks &amp; units
                </li>
                <li className="flex items-center gap-1.5">
                  &#10003; <b>Syllabus-Aligned RAG:</b> Authentic textbook excerpts
                </li>
                <li className="flex items-center gap-1.5">
                  &#10003; <b>Outcome Attribution:</b> BL, CO, PO, and PSO boxes
                </li>
                <li className="flex items-center gap-1.5">
                  &#10003; <b>Incremental Persistence:</b> Saved per question
                </li>
                <li className="flex items-center gap-1.5">
                  &#10003; <b>Rate-limit aware:</b> Auto-retry with backoff
                </li>
              </ul>
            </div>

            {jobProgress && jobProgress.errors.length > 0 && (
              <div className="border-t border-slate-100 pt-3">
                <h4 className="text-xs font-semibold text-amber-600">Slot Errors</h4>
                <ul className="mt-1 space-y-1 text-xs text-slate-500">
                  {jobProgress.errors.slice(0, 5).map((e, i) => (
                    <li key={i} className="truncate">
                      {e}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
