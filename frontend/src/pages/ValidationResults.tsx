import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../services/api";
import { Alert, PageHeader, Spinner } from "../components/ui";
import { useWorkflow } from "../context/WorkflowContext";

export default function ValidationResults() {
  const navigate = useNavigate();
  const { subjectId, pattern, questions, setQuestions, validation, setValidation } = useWorkflow();
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");

  async function validate() {
    setBusy("validate");
    setErr("");
    try {
      const r = await api.post("/validation/validate", {
        subject_id: subjectId,
        pattern,
        questions,
      });
      setValidation(r.data.validation);
    } catch (e: any) {
      setErr(e.response?.data?.error || "Validation failed");
    } finally {
      setBusy("");
    }
  }

  async function autoFix() {
    setBusy("fix");
    setErr("");
    try {
      const r = await api.post("/validation/fix", {
        subject_id: subjectId,
        pattern,
        questions,
      });
      setQuestions(r.data.questions);
      setValidation(r.data.validation);
    } catch (e: any) {
      setErr(e.response?.data?.error || "Auto-fix failed");
    } finally {
      setBusy("");
    }
  }

  return (
    <div>
      <PageHeader
        title="Validation Results"
        subtitle="Marks, structure, coverage, duplicates, similarity and hallucination checks"
        actions={
          <div className="flex gap-2">
            <button className="btn-primary" disabled={!!busy || !questions.length} onClick={validate}>
              {busy === "validate" ? "Validating…" : "Validate"}
            </button>
            <button className="btn-ghost" disabled={!!busy || !validation} onClick={autoFix}>
              {busy === "fix" ? "Fixing…" : "Fix Automatically"}
            </button>
            <button className="btn-ghost" onClick={() => navigate("/review")}>
              Regenerate Question
            </button>
          </div>
        }
      />
      {err && <Alert kind="error">{err}</Alert>}
      {busy && <Spinner label="Running validation engine…" />}
      {!validation && !busy && <Alert kind="info">Click Validate to run all checks.</Alert>}

      {validation && (
        <>
          <div className="mb-4">
            <Alert kind={validation.valid ? "success" : "error"}>
              {validation.valid
                ? "✓ Paper passed all validation checks."
                : `✗ ${validation.errors.length} issue(s) found.`}
            </Alert>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="card">
              <h3 className="mb-3 font-medium">Checks</h3>
              <ul className="space-y-1 text-sm">
                {validation.checks.map((c: any, i: number) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className={c.ok ? "text-green-600" : "text-red-600"}>
                      {c.ok ? "✓" : "✗"}
                    </span>
                    <span>
                      {c.check}{" "}
                      <span className="text-xs text-slate-400">
                        ({typeof c.detail === "object" ? JSON.stringify(c.detail) : c.detail})
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="card">
              <h3 className="mb-3 font-medium">Errors</h3>
              {validation.errors.length === 0 ? (
                <p className="text-sm text-green-700">None 🎉</p>
              ) : (
                <ul className="space-y-1 text-sm text-red-700">
                  {validation.errors.map((e: any, i: number) => (
                    <li key={i}>✗ {e.message}</li>
                  ))}
                </ul>
              )}
              <div className="mt-4 text-xs text-slate-500">
                <p>Total marks: {validation.summary.total_marks}/{validation.summary.expected_marks}</p>
                <p>Units covered: {validation.summary.units_covered.join(", ")}</p>
                <p>Missing units: {validation.summary.missing_units.join(", ") || "none"}</p>
              </div>
            </div>
          </div>

          {validation.valid && (
            <button className="btn-primary mt-4" onClick={() => navigate("/paper")}>
              Proceed to Create Paper →
            </button>
          )}
        </>
      )}
    </div>
  );
}
