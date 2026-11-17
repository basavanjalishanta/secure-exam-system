import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { Alert } from "../components/ui";

export default function Login() {
  const { login, verifyOtp, user } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [step, setStep] = useState<"password" | "otp">("password");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) navigate("/dashboard", { replace: true });

  async function submitPassword(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email, password);
      setStep("otp");
    } catch (err: any) {
      setError(err.response?.data?.error || "Could not sign in");
    } finally {
      setBusy(false);
    }
  }

  async function submitOtp(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await verifyOtp(email, otp);
      navigate("/dashboard");
    } catch (err: any) {
      setError(err.response?.data?.error || "OTP verification failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <h1 className="text-xl font-semibold text-brand-700">SecureExam AI</h1>
          <p className="text-sm text-slate-500">Examination Question Paper Management</p>
        </div>
        <form onSubmit={step === "password" ? submitPassword : submitOtp} className="card space-y-4">
          <h2 className="text-lg font-medium">{step === "password" ? "Sign in" : "Email verification"}</h2>
          {error && <Alert kind="error">{error}</Alert>}
          {step === "password" ? (
            <>
              <div>
                <label className="label">Email</label>
                <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
              </div>
              <div>
                <label className="label">Password</label>
                <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
              </div>
              <button className="btn-primary w-full" disabled={busy}>
                {busy ? "Checking…" : "Continue"}
              </button>
              <p className="text-center text-sm text-slate-500">
                No account?{" "}
                <Link to="/register" className="text-brand-600 hover:underline">Register as lecturer</Link>
              </p>
            </>
          ) : (
            <>
              <p className="text-sm text-slate-600">A 6-digit verification code has been sent to <strong>{email}</strong>. It expires in 5 minutes.</p>
              <div>
                <label className="label">Email verification code</label>
                <input
                  className="input"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\\D/g, "").slice(0, 6))}
                  placeholder="Enter 6-digit code"
                  required
                />
              </div>
              <button className="btn-primary w-full" disabled={busy || otp.length !== 6}>
                {busy ? "Verifying…" : "Verify and sign in"}
              </button>
              <button type="button" className="w-full text-sm text-brand-600 hover:underline" onClick={() => { setStep("password"); setOtp(""); setError(""); }}>
                Back to sign in
              </button>
            </>
          )}
        </form>
      </div>
    </div>
  );
}
