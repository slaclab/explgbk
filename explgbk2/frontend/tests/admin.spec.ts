import { expect, test } from "@playwright/test"

test("Admin page is accessible and shows correct title", async ({ page }) => {
  await page.goto("/admin")
  await expect(page.getByRole("heading", { name: "Users" })).toBeVisible()
  await expect(
    page.getByText("Manage user accounts and permissions"),
  ).toBeVisible()
})

test("Add User button is not visible", async ({ page }) => {
  await page.goto("/admin")
  await expect(page.getByRole("button", { name: "Add User" })).not.toBeVisible()
})

test("Superuser can access admin page", async ({ page }) => {
  await page.goto("/admin")

  await expect(page.getByRole("heading", { name: "Users" })).toBeVisible()
})
