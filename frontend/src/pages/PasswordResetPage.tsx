import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

export function PasswordResetPage() {
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<"request" | "confirm">("request");

  async function requestReset(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const result = await api<{ message: string; reset_token?: string }>("/auth/password-reset/request", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      setMessage(result.message);
      if (result.reset_token) {
        setToken(result.reset_token);
        setStep("confirm");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    }
  }

  async function confirmReset(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/auth/password-reset/confirm", {
        method: "POST",
        body: JSON.stringify({ token, new_password: newPassword }),
      });
      setMessage("Password updated. You can sign in with your new password.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
    }
  }

  return (
    <div className="login-shell">
      <div className="login-card">
        <h1>Reset password</h1>
        {message && <div className="banner banner-success">{message}</div>}
        {error && <div className="banner banner-error">{error}</div>}

        {step === "request" ? (
          <form onSubmit={requestReset} className="login-form">
            <label>
              Email
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </label>
            <button className="btn-primary login-btn" type="submit">Send reset link</button>
          </form>
        ) : (
          <form onSubmit={confirmReset} className="login-form">
            <label>
              Reset token
              <input value={token} onChange={(e) => setToken(e.target.value)} required />
            </label>
            <label>
              New password
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                minLength={8}
                required
              />
            </label>
            <button className="btn-primary login-btn" type="submit">Update password</button>
          </form>
        )}

        <p className="login-sub"><Link to="/login">Back to sign in</Link></p>
      </div>
    </div>
  );
}
