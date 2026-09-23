import { test, expect } from "@playwright/test";

test("landing page renders product headline", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Runtime authorization for AI agents/i })).toBeVisible();
  await expect(page.getByRole("link", { name: "Sign in", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Create organization" })).toBeVisible();
});
