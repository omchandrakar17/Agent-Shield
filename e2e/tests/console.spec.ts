import { test, expect } from "@playwright/test";

test.describe("operations console", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/console");
    await expect(page.getByText(/Live Support Agent Demo/i)).toBeVisible();
  });

  test("loads overview and agent runner demo", async ({ page }) => {
    await expect(page.getByRole("button", { name: /Run Agent → Shield → Tools/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Demo Attack/i })).toBeVisible();
  });

  test("runs order lookup through shield gateway", async ({ page }) => {
    await page.getByLabel(/User Request/i).fill("Where is order 2481?");
    await page.getByRole("button", { name: /Run Agent → Shield → Tools/i }).click();

    await expect(page.locator("pre.audit-data")).toContainText(/"planner"/, { timeout: 15_000 });
    await expect(page.locator("pre.audit-data")).toContainText(/"tool_calls"/);
    await expect(page.locator("pre.audit-data")).toContainText(/get_order|EXECUTED|ALLOWED/i);
  });

  test("blocks prompt-injection attack demo", async ({ page }) => {
    await page.getByRole("button", { name: /Demo Attack/i }).click();
    await page.getByRole("button", { name: /Run Agent → Shield → Tools/i }).click();

    const output = page.locator("pre.audit-data");
    await expect(output).toContainText(/"prompt_injection_detected": true/i, { timeout: 15_000 });
    await expect(output).toContainText(/BLOCKED/i);
  });
});
