import { useEffect, useState } from "react";
import api from "../services/api";
import { PageHeader } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { useWorkflow } from "../context/WorkflowContext";

export default function Settings() {
  const { user } = useAuth();
  const { reset } = useWorkflow();
  const [health, setHealth] = useState<any>(null);

  useEffect(() => {
    api.get("/health").then((r) => setHealth(r.data));
  }, []);

  return (
    <div>
      <PageHeader title="Settings" subtitle="Account and system information" />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card">
          <h3 className="mb-2 font-medium">Account</h3>
          <p className="text-sm">Name: {user?.name}</p>
          <p className="text-sm">Email: {user?.email}</p>
          <p className="text-sm">Role: {user?.role}</p>
        </div>
        <div className="card">
          <h3 className="mb-2 font-medium">System</h3>
          <p className="text-sm">API status: {health?.status ?? "…"}</p>
          <p className="text-sm">MongoDB connected: {String(health?.mongo)}</p>
          <p className="text-sm">AI provider: {health?.ai_provider}</p>
        </div>
        <div className="card">
          <h3 className="mb-2 font-medium">Workflow</h3>
          <p className="text-sm text-slate-500">
            Clear the current generation workflow (subject stays selected).
          </p>
          <button className="btn-ghost mt-3" onClick={reset}>
            Reset workflow
          </button>
        </div>
        <div className="card">
          <h3 className="mb-2 font-medium">Security notes</h3>
          <ul className="list-disc pl-5 text-sm text-slate-600">
            <li>Passwords hashed with bcrypt</li>
            <li>JWT bearer tokens, role-based route guards</li>
            <li>Generated papers encrypted with AES-256-GCM</li>
            <li>Plaintext PDFs are never persisted</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
