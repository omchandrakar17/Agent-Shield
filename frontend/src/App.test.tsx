import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { App } from "./App";

function renderApp() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>
  );
}

describe("AgentShield Console App", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/auth/config")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ auth_mode: "disabled", environment: "test" }),
          });
        }
        if (url.includes("/actions/act-101/trace")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                action_id: "act-101",
                status: "EXECUTED",
                latency_ms: 12.4,
                matched_rule_id: "rule-read-order",
                evidence: { decision_basis: "Read-only lookup" },
                spans: [
                  {
                    id: "span-1",
                    span_name: "policy_evaluation",
                    start_time: "2026-09-22T05:00:00Z",
                    end_time: "2026-09-22T05:00:00.012Z",
                    duration_ms: 12.4,
                    status: "OK",
                  },
                ],
                audit_events: [],
              }),
          });
        }
        if (url.includes("/actions")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve([
                {
                  id: "act-101",
                  agent_id: "support-agent",
                  action_type: "get_order",
                  target: "order:2481",
                  payload: {},
                  idempotency_key: "k1",
                  arguments_hash: "sha256:abc123456789012345",
                  status: "EXECUTED",
                  risk_level: "LOW",
                  reason: "Read-only sandbox lookup",
                  matched_rule_id: "rule-read-order",
                  latency_ms: 12.4,
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                },
              ]),
          });
        }
        if (url.includes("/approvals")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve([
                {
                  id: "apr-99",
                  action_id: "act-101",
                  status: "PENDING",
                  arguments_hash: "sha256:def456789012345678",
                  requested_at: new Date().toISOString(),
                  expires_at: new Date(Date.now() + 900000).toISOString(),
                },
              ]),
          });
        }
        if (url.includes("/audit")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
        }
        if (url.includes("/controls")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ enabled: false, reason: "", actor: "system" }),
          });
        }
        if (url.includes("/policies")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve([
                {
                  id: "default-policy",
                  name: "Default Agent Guardrail Policy",
                  version: 1,
                  status: "PUBLISHED",
                  is_active: true,
                  created_by: "system",
                  rules: [
                    {
                      id: "rule-read-order",
                      action: "get_order",
                      effect: "ALLOW",
                      risk_level: "LOW",
                      reason: "Read-only sandbox lookup",
                    },
                  ],
                  created_at: new Date().toISOString(),
                },
              ]),
          });
        }
        if (url.includes("/agents")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve([
                {
                  id: "support-agent",
                  name: "Support Agent",
                  owner: "platform",
                  version: "1",
                  status: "ACTIVE",
                  allowed_tools: ["get_order"],
                },
              ]),
          });
        }
        if (url.includes("/tools")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve([
                {
                  id: "get_order",
                  name: "get_order",
                  version: "1.0",
                  risk_class: "LOW",
                  permission_scope: "order:read",
                  endpoint: "/orders",
                  enabled: true,
                },
              ]),
          });
        }
        if (url.includes("/incidents")) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
        }
        if (url.includes("/evaluations")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ total_cases: 10, categories: { safe_read: 3 } }),
          });
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
      })
    );
  });

  it("renders brand, overview cards, and navigation tabs", async () => {
    renderApp();

    await waitFor(() => {
      expect(screen.getByText(/WELCOME BACK/i)).toBeDefined();
    });
    expect(screen.getAllByText("AgentShield").length).toBeGreaterThan(0);
    expect(screen.getByText("Total Agents")).toBeDefined();
    expect(screen.getAllByText("Pending Approvals").length).toBeGreaterThan(0);
    expect(screen.getByText("Recent Activity")).toBeDefined();
  });

  it("renders approval queue and handles decision", async () => {
    renderApp();
    await waitFor(() => expect(screen.getByText(/WELCOME BACK/i)).toBeDefined());

    const approvalsTab = screen.getByRole("button", { name: /^Approvals/i });
    fireEvent.click(approvalsTab);

    expect(screen.getByText("Approval Management")).toBeDefined();
    await waitFor(() => {
      expect(screen.getByText("apr-99")).toBeDefined();
    });

    const approveButton = screen.getByRole("button", { name: /Approve Exact Action/i });
    expect(approveButton).toBeDefined();
    fireEvent.click(approveButton);
  });

  it("renders policy center and kill switch state", async () => {
    renderApp();
    await waitFor(() => expect(screen.getByText(/WELCOME BACK/i)).toBeDefined());

    const policiesTab = screen.getByRole("button", { name: /^Policies/i });
    fireEvent.click(policiesTab);

    expect(screen.getByText("Policy Rule Engine & Lifecycle")).toBeDefined();
    await waitFor(() => {
      expect(screen.getByText("Default Agent Guardrail Policy")).toBeDefined();
      expect(screen.getByText("PUBLISHED")).toBeDefined();
    });

    const secTab = screen.getByRole("button", { name: /^Security Events/i });
    fireEvent.click(secTab);

    expect(screen.getByRole("heading", { name: "Security Events" })).toBeDefined();
    expect(screen.getByText("ARMED & READY")).toBeDefined();
  });

  it("renders trace detail with spans", async () => {
    renderApp();
    await waitFor(() => expect(screen.getByText(/WELCOME BACK/i)).toBeDefined());

    fireEvent.click(screen.getByRole("button", { name: /View Execution Trace/i }));

    await waitFor(() => {
      expect(screen.getByText(/Execution Trace:/i)).toBeDefined();
      expect(screen.getByText("policy_evaluation")).toBeDefined();
    });
  });
});
