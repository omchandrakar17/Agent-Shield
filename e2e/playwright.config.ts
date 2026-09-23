import { defineConfig, devices } from "@playwright/test";

const backendPort = process.env.E2E_BACKEND_PORT || "8000";
const frontendPort = process.env.E2E_FRONTEND_PORT || "5173";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  timeout: 60_000,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL: `http://localhost:${frontendPort}`,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: `python -m uvicorn app.main:app --app-dir ../backend --port ${backendPort}`,
      url: `http://localhost:${backendPort}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        ...process.env,
        AGENTSHIELD_AUTH_MODE: "disabled",
        AGENTSHIELD_DATABASE_URL: "sqlite:///./e2e-agentshield.db",
        AGENTSHIELD_AGENT_PLANNER: "keyword",
      },
    },
    {
      command: `npm run dev -- --port ${frontendPort} --host 127.0.0.1`,
      url: `http://localhost:${frontendPort}`,
      cwd: "../frontend",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
