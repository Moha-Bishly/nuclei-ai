import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { register } from "../api";

export default function RegisterPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register(username, email, password);
      navigate("/login");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="auth-brand">⬡ NucleiAI</div>
        <h2 className="auth-title">Create account</h2>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="field-label" htmlFor="reg-username">Username</label>
          <input
            id="reg-username"
            className="field-input"
            type="text"
            required
            minLength={3}
            maxLength={50}
            value={username}
            onChange={e => setUsername(e.target.value)}
            autoComplete="username"
            aria-label="Username"
          />
          <label className="field-label" htmlFor="reg-email">Email</label>
          <input
            id="reg-email"
            className="field-input"
            type="email"
            required
            value={email}
            onChange={e => setEmail(e.target.value)}
            autoComplete="email"
            aria-label="Email"
          />
          <label className="field-label" htmlFor="reg-password">Password <span className="field-hint">(uppercase, lowercase, number, special character)</span></label>
          <input
            id="reg-password"
            className="field-input"
            type="password"
            required
            minLength={8}
            value={password}
            onChange={e => setPassword(e.target.value)}
            autoComplete="new-password"
            aria-label="Password"
          />
          {error && <div className="error">{error}</div>}
          <button className="btn btn-full" type="submit" disabled={busy}>
            {busy ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="auth-footer">
          Already have an account? <Link to="/login" className="link-btn">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
