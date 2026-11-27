import { test, expect } from '@playwright/test';

test('W4 shopping scenario', async ({ page }) => {
  await test.step('Open the home page', async () => {
    await page.goto('/');
    await expect(page).toHaveURL(/^https:\/\//);
    await expect(page.locator('#_desktop_logo img.logo')).toBeVisible();
  });
});
