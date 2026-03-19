// No login page exists — auth is handled by Dex IDP.
// The setup project just saves an empty storage state so the
// auth-dependent projects can still declare a dependency on 'setup'.
import { test as setup } from "@playwright/test"

const authFile = "playwright/.auth/user.json"

setup("authenticate", async ({ page }) => {
  await page.context().storageState({ path: authFile })
})
