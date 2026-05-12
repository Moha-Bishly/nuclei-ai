import { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { getMe } from "../api";
import { useAuth } from "../contexts/AuthContext";

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://127.0.0.1:8000";

export default function OAuthCallbackPage() {
  const { login: authLogin } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const hasRun = useRef(false);

  useEffect(() => {
    if (hasRun.current) return;
    hasRun.current = true;

    const code = params.get("code");
    if (!code) {
      navigate("/login?error=oauth_failed");
      return;
    }
    fetch(`${API_BASE}/auth/oauth/exchange`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    })
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(({ access_token }: { access_token: string }) => {
        localStorage.setItem("token", access_token);
        return getMe().then(user => {
          authLogin(access_token, user);
          navigate("/dashboard");
        });
      })
      .catch(() => {
        localStorage.removeItem("token");
        navigate("/login?error=oauth_failed");
      });
  }, [params, authLogin, navigate]);

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="status-line"><div className="spinner" /> Completing sign-in…</div>
      </div>
    </div>
  );
}
