import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { Alert } from "../components/ui";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (form.password.length < 8) return setError("Password must be at least 8 characters");
    setBusy(true);
    try {
      await register(form.name, form.email, form.password);
      navigate("/dashboard");
    } catch (err: any) {
      setError(err.response?.data?.error || "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <form onSubmit={submit} className="card w-full max-w-sm space-y-4">
        <h2 className="text-lg font-medium">Create lecturer account</h2>
        <p className="text-xs text-slate-500">
          The very first account created on a fresh system becomes the admin.
        </p>
        {error && <Alert kind="error">{error}</Alert>}
        {(["name", "email", "password"] as const).map((f) => (
          <div key={f}>
            <label className="label capitalize">{f}</label>
            <input
              className="input"
              type={f === "password" ? "password" : f === "email" ? "email" : "text"}
              value={form[f]}
              onChange={(e) => setForm({ ...form, [f]: e.target.value })}
              required
            />
          </div>
        ))}
        <button className="btn-primary w-full" disabled={busy}>
          {busy ? "Creating…" : "Register"}
        </button>
        <p className="text-center text-sm text-slate-500">
          Have an account?{" "}
          <Link to="/login" className="text-brand-600 hover:underline">
            Sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
