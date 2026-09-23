import { test, expect } from "@playwright/test";

test.describe("authenticated console (local auth)", () => {
  test.use({
    baseURL: process.env.E2E_AUTH_BASE_URL || "http://localhost:5173",
  });

  test.skip(!process.env.E2E_AUTH_MODE, "Set E2E_AUTH_MODE=local to run login E2E against a local-auth stack");

  test("operator can sign in and reach console", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/Email/i).fill(process.env.E2E_OPERATOR_EMAIL || "operator@agentshield.example");
    await page.getByLabel(/Password/i).fill(process.env.E2E_OPERATOR_PASSWORD || "agentshield2026");
    await page.getByRole("button", { name: /Sign in to Console/i }).click();

    await expect(page).toHaveURL(/\/console/);
    await expect(page.getByText(/Live Support Agent Demo/i)).toBeVisible();
  });
});
