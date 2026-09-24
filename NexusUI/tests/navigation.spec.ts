import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import type { Research, Result } from '../src/data/research';

const api = '/api/backend';
test('landing preserves the approved dark design and leads to the library', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.landing')).toHaveCSS('background-color', 'rgb(12, 12, 14)');
  await expect(page.locator('aside')).toHaveCount(0);
  await page.getByRole('link', { name: 'How it works', exact: true }).click();
  await expect(page).toHaveURL('/#how-it-works');
  await page.getByRole('link', { name: 'Start researching', exact: true }).click();
  await expect(page).toHaveURL('/research');
  await expect(page.getByRole('heading', { name: 'A space for every question.' })).toBeVisible();
});

test('workspace creation, draft persistence, library search, and empty screens use the database', async ({
  page,
}) => {
  const name = 'Browser workspace ' + randomUUID().slice(0, 8);
  await page.goto('/research/new');
  await page.getByLabel('Research name', { exact: true }).fill(name);
  await page
    .getByLabel('What are you exploring?', { exact: false })
    .fill('An isolated browser verification workspace.');
  await page.getByRole('button', { name: 'Create research' }).click();
  await expect(page).toHaveURL(/\/research\/[a-f0-9-]{36}$/);
  const workspaceUrl = page.url();
  await expect(page.getByRole('heading', { name: 'No runs yet' })).toBeVisible();
  await page
    .getByLabel('Research question', { exact: true })
    .fill('How should we check citation quality?');
  await page.getByRole('button', { name: 'Evidence Only', exact: true }).click();
  await page.getByLabel('Passages / source').selectOption('8');
  await page.getByRole('button', { name: 'Save draft' }).click();
  await expect(
    page.getByText('Draft saved to your local database.', { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('Research question', { exact: true })).toHaveValue(
    'How should we check citation quality?',
  );
  await expect(page.getByRole('button', { name: 'Evidence Only', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await expect(page.getByRole('button', { name: 'Run Research', exact: true })).toBeDisabled();
  await page.getByRole('link', { name: 'Back to all research', exact: true }).click();
  await page.getByRole('button', { name: 'List view' }).click();
  await page.getByLabel('Search research', { exact: true }).fill(name);
  await expect(page.locator('article.research-card')).toHaveCount(1);
  await page.getByRole('link', { name: 'Open ' + name, exact: true }).click();
  await expect(page).toHaveURL(workspaceUrl);
  for (const [route, title] of [
    ['sources', 'Source library'],
    ['runs', 'Research runs'],
    ['evidence', 'Evidence explorer'],
    ['reports', 'Research reports'],
    ['graph', 'Research graph'],
    ['evaluation', 'Evaluation'],
    ['settings', 'Settings'],
  ]) {
    await page.goto(workspaceUrl + '/' + route);
    await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
    await expect(page.getByText('architecture.pdf', { exact: true })).toHaveCount(0);
  }
  await page.getByLabel('Name', { exact: true }).fill(name + ' renamed');
  await page.getByRole('button', { name: 'Save workspace', exact: true }).click();
  await expect(page.getByRole('status')).toHaveText('Workspace saved.');
  await page.reload();
  await expect(page.locator('.workspace-title')).toHaveText(name + ' renamed');
});

test('mobile layout, command navigation, and offline errors are usable', async ({
  page,
  request,
}) => {
  const response = await request.post(api + '/v1/projects', {
    data: { title: 'Mobile browser check ' + randomUUID().slice(0, 6) },
  });
  const project: Research = await response.json();
  const base = '/research/' + project.id;
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(base);
  await expect(page.locator('.research-sidebar')).toHaveCSS('width', '56px');
  await page.keyboard.press('ControlOrMeta+k');
  await page.getByLabel('Search commands and research').fill('Evaluation');
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(base + '/evaluation');
  for (const route of [
    '/',
    '/research',
    '/research/new',
    base,
    base + '/sources',
    base + '/settings',
  ]) {
    await page.goto(route);
    await expect(page.locator('main').first()).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      390,
    );
  }
  await page.route('**/api/backend/v1/projects**', (route) => route.abort());
  await page.goto('/research');
  await expect(page.locator('.error-notice')).toContainText('Cannot reach the local backend');
});

test('real upload → agentic run → browser close → citations → reports → review', async ({
  page,
  context,
  request,
}) => {
  test.skip(
    !process.env.NEXUS_LIVE_E2E,
    'Set NEXUS_LIVE_E2E=1 to use the local worker and real Azure.',
  );
  test.setTimeout(180000);
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  const name = 'End-to-end browser research ' + randomUUID().slice(0, 6);
  await page.goto('/research/new');
  await page.getByLabel('Research name', { exact: true }).fill(name);
  await page.getByRole('button', { name: 'Create research' }).click();
  await expect(page).toHaveURL(/\/research\/[a-f0-9-]{36}$/);
  const projectId = page.url().split('/').at(-1)!;
  const base = '/research/' + projectId;
  await page.getByRole('link', { name: 'Sources', exact: true }).click();
  const documents: { name: string; base64: string }[] = JSON.parse(
    execFileSync('../.venv/bin/python', ['../scripts/smoke_documents.py'], { encoding: 'utf8' }),
  );
  await page.getByLabel('Upload documents').setInputFiles(
    documents.map((file) => ({
      name: file.name,
      mimeType: file.name.endsWith('.pdf')
        ? 'application/pdf'
        : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      buffer: Buffer.from(file.base64, 'base64'),
    })),
  );
  const alpha = page.getByRole('checkbox', { name: 'Select alpha-verification.pdf', exact: true });
  const beta = page.getByRole('checkbox', { name: 'Select beta-verification.docx', exact: true });
  await expect(alpha).toBeEnabled({ timeout: 90000 });
  await expect(beta).toBeEnabled({ timeout: 90000 });
  await alpha.check();
  await expect(alpha).toBeChecked();
  await expect(beta).toBeEnabled();
  await beta.check();
  await expect(beta).toBeChecked();
  await expect(beta).toBeEnabled();
  await page.getByRole('link', { name: 'Research with selected sources' }).click();
  await page
    .getByLabel('Research question', { exact: true })
    .fill('Compare the record retention periods and request execution in Alpha and Beta.');
  await expect(page.getByRole('button', { name: 'Run Research', exact: true })).toBeEnabled();
  const submission = page.waitForResponse(
    (response) =>
      response.url().endsWith('/v1/research/jobs') && response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Run Research', exact: true }).click();
  const job = await (await submission).json();
  expect(job.status).toBe('created');
  await expect(page).toHaveURL(base + '/runs/' + job.job_id);
  await page.close();
  await expect
    .poll(
      async () =>
        (await (await request.get(api + '/v1/research/jobs/' + job.job_id)).json()).status,
      { timeout: 100000, intervals: [1000, 2000] },
    )
    .toMatch(/^completed/);
  const reopened = await context.newPage();
  reopened.on('pageerror', (error) => errors.push(error.message));
  await reopened.goto(base + '/runs/' + job.job_id);
  await expect(
    reopened.getByRole('heading', { name: 'Research findings', exact: true }),
  ).toBeVisible();
  await expect(reopened.locator('.result-content')).toContainText('30');
  await expect(reopened.locator('.result-content')).toContainText('90');
  await reopened.getByRole('button', { name: '[E1]', exact: true }).first().click();
  await expect(reopened.locator('.citation-inspector')).toBeVisible();
  await reopened
    .locator('.citation-inspector')
    .getByRole('link', { name: 'Open exact passage' })
    .click();
  await expect(reopened.getByRole('heading', { name: 'Exact passage', exact: true })).toBeVisible();
  await expect(reopened.locator('.passage-inspector blockquote')).toContainText(/Alpha|Beta/);
  await reopened.goto(base + '/runs/' + job.job_id);
  await reopened.getByRole('tab', { name: 'Plan & execution', exact: true }).click();
  await expect(reopened.locator('.react-flow__node')).not.toHaveCount(0);
  await reopened.locator('.task-row').first().click();
  await expect(reopened.getByText('Attempt 1', { exact: true })).toBeVisible();
  await reopened.getByText('Event history', { exact: true }).click();
  await expect(reopened.locator('.event-log')).toContainText('job completed');
  await reopened.locator('.workspace-scroll').evaluate((element) => {
    element.scrollTop = 0;
  });
  await reopened.screenshot({ path: 'test-results/mvp3-execution.png', fullPage: true });
  await reopened.getByRole('link', { name: 'Reports', exact: true }).click();
  await expect(reopened.getByRole('heading', { name: 'Research reports' })).toBeVisible();
  const download = reopened.waitForEvent('download');
  await reopened.getByRole('link', { name: 'JSON', exact: true }).click();
  expect((await download).suggestedFilename()).toContain(job.job_id);
  await reopened.getByRole('link', { name: 'Evaluation', exact: true }).click();
  await reopened.getByRole('combobox', { name: 'groundedness', exact: true }).selectOption('4');
  await reopened.getByRole('combobox', { name: 'relevance', exact: true }).selectOption('5');
  await reopened.getByRole('combobox', { name: 'citation quality', exact: true }).selectOption('4');
  await reopened
    .getByLabel('Review notes', { exact: true })
    .fill('Checked the synthetic source passages in the browser.');
  await reopened.getByRole('button', { name: 'Save review', exact: true }).click();
  await expect(reopened.getByRole('status')).toHaveText('Review saved.');
  const result: Result = await (
    await request.get(api + '/v1/research/jobs/' + job.job_id + '/result')
  ).json();
  expect(result.review?.relevance).toBe(5);
  for (const route of ['evidence', 'reports', 'graph']) {
    await reopened.goto(base + '/' + route);
    await expect(reopened.getByRole('heading', { level: 1 })).toBeVisible();
  }
  await expect(reopened.locator('.react-flow__node')).not.toHaveCount(0);
  await reopened.goto(base + '/runs/' + job.job_id);
  await expect(
    reopened.getByRole('heading', { name: 'Research findings', exact: true }),
  ).toBeVisible();
  await reopened.screenshot({ path: 'test-results/mvp3-result.png', fullPage: true });
  await reopened.setViewportSize({ width: 390, height: 844 });
  await expect(reopened.locator('.research-sidebar')).toHaveCSS('width', '56px');
  await reopened.screenshot({ path: 'test-results/mvp3-mobile-result.png', fullPage: true });
  expect(await reopened.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
    390,
  );
  expect(errors).toEqual([]);
});

test('approved web research requires fresh consent and preserves visible provenance', async ({
  page,
  request,
}) => {
  test.skip(
    !process.env.NEXUS_LIVE_E2E,
    'Set NEXUS_LIVE_E2E=1 for the real public-page and Azure check.',
  );
  test.setTimeout(90000);
  const response = await request.post(api + '/v1/projects', {
    data: { title: 'Approved web browser check ' + randomUUID().slice(0, 6) },
  });
  const project: Research = await response.json();
  await page.goto('/research/' + project.id);
  await page
    .getByLabel('Research question', { exact: true })
    .fill('What is the example domain used for?');
  await page.getByRole('button', { name: 'Evidence Only', exact: true }).click();
  await page.getByText('Include approved web pages', { exact: false }).click();
  await page.getByLabel('HTTPS URLs', { exact: false }).fill('https://example.com/');
  const approve = page.getByRole('checkbox', {
    name: 'I approve fetching these pages',
    exact: false,
  });
  await expect(page.getByRole('button', { name: 'Run Research', exact: true })).toBeDisabled();
  await approve.check();
  await page.getByRole('button', { name: 'Save draft', exact: true }).click();
  await expect(
    page.getByText('Draft saved to your local database.', { exact: true }),
  ).toBeVisible();
  await page.reload();
  await page.getByText('Include approved web pages', { exact: false }).click();
  await expect(approve).not.toBeChecked();
  await expect(page.getByRole('button', { name: 'Run Research', exact: true })).toBeDisabled();
  await approve.check();
  const accepted = page.waitForResponse(
    (response) =>
      response.url().endsWith('/v1/research/jobs') && response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Run Research', exact: true }).click();
  const job = await (await accepted).json();
  await expect(page.getByRole('heading', { name: 'Retrieved evidence', exact: true })).toBeVisible({
    timeout: 60000,
  });
  await page.getByRole('tab', { name: 'Source coverage', exact: true }).click();
  await expect(page.getByText('Approved web snapshot', { exact: true })).toBeVisible();
  const result: Result = await (
    await request.get(api + '/v1/research/jobs/' + job.job_id + '/result')
  ).json();
  expect(result.external_sources[0].url).toBe('https://example.com/');
  expect(result.evidence[0].locator).toMatchObject({ url: 'https://example.com/' });
  await expect(page.getByText(result.external_sources[0].url, { exact: true })).toBeVisible();
});
