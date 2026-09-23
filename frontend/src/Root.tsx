import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { App } from "./App";
import { LandingPage } from "./pages/LandingPage";
import { DocumentationPage } from "./pages/DocumentationPage";
import { HowItWorksPage } from "./pages/HowItWorksPage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { SecurityPage } from "./pages/SecurityPage";
import { PasswordResetPage } from "./pages/PasswordResetPage";

function ConsoleRoute() {
  const { user, loading, config } = useAuth();

  if (loading) {
    return (
      <div className="login-shell">
        <div className="login-card">
          <p className="login-sub">Loading AgentShield console…</p>
        </div>
      </div>
    );
  }

  if (!user && config?.auth_mode !== "disabled") {
    return <Navigate to="/login" replace />;
  }

  return <App />;
}

export function Root() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/how-it-works" element={<HowItWorksPage />} />
        <Route path="/security" element={<SecurityPage />} />
        <Route path="/docs" element={<DocumentationPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/reset-password" element={<PasswordResetPage />} />
        <Route path="/console/*" element={<ConsoleRoute />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
