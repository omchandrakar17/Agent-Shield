const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";
const TOKEN_KEY = "agentshield_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const reqId = "req-" + Math.random().toString(36).substring(2, 9);
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "x-request-id": reqId,
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    headers,
    ...init,
  });
  const body = await response.json();
  if (!response.ok) {
    const errDetail = body.detail;
    let msg = `Request failed (${response.status})`;
    if (typeof errDetail === "object" && errDetail !== null) {
      msg = `[${errDetail.code || "ERROR"}] ${errDetail.message || "Operation rejected"} (Request: ${errDetail.request_id || reqId})`;
    } else if (typeof errDetail === "string") {
      msg = errDetail;
    }
    throw new Error(msg);
  }
  return body;
}

export async function fetchAuthConfig(): Promise<{
  auth_mode: string;
  environment: string;
  firebase?: { apiKey: string; authDomain: string; projectId: string } | null;
}> {
  const response = await fetch(`${API_BASE}/auth/config`);
  return response.json();
}
