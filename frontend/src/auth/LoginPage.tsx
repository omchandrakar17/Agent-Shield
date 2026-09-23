import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function LoginPage() {
  const navigate = useNavigate();
  const { login, loginWithGoogle, config } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
      navigate("/console");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleGoogle() {
    setSubmitting(true);
    setError(null);
    try {
      await loginWithGoogle();
      navigate("/console");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Google sign-in failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-shell">
      <div className="login-card">
        <div className="login-brand">
          <span className="login-logo">AS</span>
          <div>
            <h1>AgentShield</h1>
            <p>Runtime Control Plane for Secure AI Agents</p>
          </div>
        </div>

        <span className="login-env">{config?.environment?.toUpperCase() || "DEVELOPMENT"}</span>

        <p className="login-sub">
          Sign in to access the operations console — approvals, policy center, security incidents, and audit traces.
        </p>

        {error && <div className="banner banner-error">{error}</div>}

        <form onSubmit={handleSubmit} className="login-form">
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="operator@agentshield.example"
              required
              autoComplete="username"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              autoComplete="current-password"
            />
          </label>
          <button className="btn-primary login-btn" type="submit" disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in to Console"}
          </button>
        </form>

        {config?.firebase && (
          <button className="btn-outline login-google" type="button" onClick={() => void handleGoogle()} disabled={submitting}>
            Sign in with Google
          </button>
        )}

        <p className="login-sub">
          <Link to="/register">Create organization</Link> · <Link to="/reset-password">Forgot password?</Link>
        </p>
      </div>
    </div>
  );
}
