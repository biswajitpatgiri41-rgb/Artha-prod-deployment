import { expect, test } from '@playwright/test';

const cpiObservations = [
  {
    date: '2026-08-01',
    value: 5.2,
    series_id: 'cpi_yoy',
    source: 'MoSPI',
    unit: 'percent',
    source_url: 'https://www.mospi.gov.in/',
    retrieved_at: '2026-09-14T08:00:00Z',
  },
  {
    date: '2026-09-01',
    value: 5.5,
    series_id: 'cpi_yoy',
    source: 'MoSPI',
    unit: 'percent',
    source_url: 'https://www.mospi.gov.in/',
    retrieved_at: '2026-10-14T08:00:00Z',
  },
];

test('dashboard reports CPI observation count and avoids presenting a point baseline as an interval', async ({ page }) => {
  await page.route('https://artha-ai-api.vercel.app/series/**', async (route) => {
    const url = new URL(route.request().url());
    const seriesId = url.pathname.split('/').at(-1);
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        series_id: seriesId,
        observations: seriesId === 'cpi_yoy' ? cpiObservations : [],
      }),
    });
  });
  await page.route('https://artha-ai-api.vercel.app/forecast**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        model: 'seasonal_naive',
        origin: '2026-09-01',
        horizon_months: 2,
        forecasts: [{ step: 1, value: 4.9 }, { step: 2, value: 5.1 }],
        source: 'MoSPI',
        unit: 'percent',
      }),
    });
  });
  await page.goto('/');
  await expect(page.getByText('2 CPI observations')).toBeVisible();
  await expect(page.getByText('Latest observed: 2026-09-01')).toBeVisible();
  await expect(page.getByText(/uncertainty interval not estimated/)).toBeVisible();
  await expect(page.getByText('0 macro observations')).toHaveCount(0);
  await expect(page.getByText('Uncertainty band')).toHaveCount(0);
});

test('dashboard discloses a failed series request without substituting demo values', async ({ page }) => {
  await page.route('https://artha-ai-api.vercel.app/series/**', async (route) => {
    const seriesId = new URL(route.request().url()).pathname.split('/').at(-1);
    if (seriesId === 'repo_rate') {
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'temporarily unavailable' }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ observations: seriesId === 'cpi_yoy' ? cpiObservations : [] }) });
  });
  await page.route('https://artha-ai-api.vercel.app/forecast**', async (route) => {
    await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'temporarily unavailable' }) });
  });

  await page.goto('/');
  await expect(page.getByText(/Some live data could not be loaded \(repo_rate\)/)).toBeVisible();
  await expect(page.getByText('Unavailable · no observed data').first()).toBeVisible();
  await expect(page.getByText('Demo summary · mock')).toHaveCount(0);
});
