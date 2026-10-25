import { expect, test } from '@playwright/test';

test('main frontend sends sign-in details to its same-origin BFF and returns to the dashboard', async ({ page }) => {
  let requestBody: Record<string, unknown> | null = null;
  await page.route('**/api/auth/login', async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ user: { email: 'researcher@example.com', role: 'ADMIN' } }),
    });
  });

  await page.goto('/login');
  await page.getByLabel('Email').fill('researcher@example.com');
  await page.getByLabel('Password').fill('test-password-only');
  await page.getByLabel(/Authenticator code/).fill('123456');
  await page.getByRole('button', { name: /sign in securely/i }).click();

  await expect(page).toHaveURL('http://localhost:3000/');
  expect(requestBody).toEqual({ email: 'researcher@example.com', password: 'test-password-only', totp_code: '123456' });
});

test('main frontend shows a safe sign-in error and clears the password after rejection', async ({ page }) => {
  await page.route('**/api/auth/login', async (route) => {
    await route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ error: 'Invalid credentials or authenticator code' }) });
  });
  await page.goto('/login');
  await page.getByLabel('Email').fill('researcher@example.com');
  await page.getByLabel('Password').fill('wrong-password');
  await page.getByRole('button', { name: /sign in securely/i }).click();
  await expect(page.getByText('Invalid credentials or authenticator code')).toBeVisible();
  await expect(page.getByLabel('Password')).toHaveValue('');
});
