import { expect, test } from '@playwright/test';

const transformer = '/research/transformer-architectures';
const retrieval = '/research/retrieval-strategies';

test('the public landing page leads to the library and a scoped demo', async ({
  page,
}) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    'Research as aconnected story,not a collectionof answers.',
  );
  await expect(page.locator('aside')).toHaveCount(0);
  await page.getByRole('link', { name: 'How it works', exact: true }).click();
  await expect(page).toHaveURL('/#how-it-works');
  await expect(
    page.getByRole('heading', { name: 'From a question to understanding.' }),
  ).toBeInViewport();
  await page
    .getByRole('link', { name: 'Start researching', exact: true })
    .click();
  await expect(page).toHaveURL('/research');
  await expect(
    page.getByRole('heading', { name: 'A space for every question.' }),
  ).toBeVisible();
  await expect(page.locator('article.research-card')).toHaveCount(3);
  await page.getByRole('link', { name: 'Nexus home', exact: true }).click();
  await page.getByRole('link', { name: 'Explore demo', exact: true }).click();
  await expect(page).toHaveURL(transformer);
  await expect(page.locator('.workspace-title')).toHaveText(
    'Transformer architectures',
  );
});

test('the landing page shares the Nexus palette, buttons, and logo', async ({
  page,
}) => {
  await page.goto('/');
  await expect(page.locator('.landing')).toHaveCSS(
    'background-color',
    'rgb(12, 12, 14)',
  );
  await expect(page.locator('.landing')).toHaveCSS(
    'color',
    'rgb(240, 237, 232)',
  );
  await expect(page.locator('.landing-hero h1 em')).toHaveCSS(
    'color',
    'rgb(59, 158, 255)',
  );
  await expect(page.locator('.preview-window')).toHaveCSS(
    'background-color',
    'rgb(17, 17, 22)',
  );
  const logoBackground = await page
    .locator('.landing-header .nexus-mark')
    .evaluate((element) => getComputedStyle(element).backgroundImage);
  const primaryButton = page.getByRole('link', {
    name: 'Start researching',
    exact: true,
  });
  await expect(primaryButton).toHaveCSS(
    'background-color',
    'rgb(50, 142, 233)',
  );
  await expect(page.locator('.landing-nav-cta')).toHaveCSS(
    'background-color',
    'rgb(50, 142, 233)',
  );
  await primaryButton.hover();
  await expect(primaryButton).toHaveCSS(
    'background-color',
    'rgb(40, 122, 204)',
  );
  await page.getByRole('link', { name: 'Explore demo', exact: true }).hover();
  await expect(
    page.getByRole('link', { name: 'Explore demo', exact: true }),
  ).toHaveCSS('background-color', 'rgb(30, 30, 39)');

  await primaryButton.click();
  await expect(page).toHaveURL('/research');
  await expect(page.locator('.research-library-page')).toHaveCSS(
    'background-color',
    'rgb(12, 12, 14)',
  );
  await expect(page.locator('.library-header .nexus-mark')).toHaveCSS(
    'background-image',
    logoBackground,
  );
  const newResearchButton = page.getByRole('link', {
    name: 'New Research',
    exact: true,
  });
  await expect(newResearchButton).toHaveCSS(
    'background-color',
    'rgb(50, 142, 233)',
  );
  await newResearchButton.hover();
  await expect(newResearchButton).toHaveCSS(
    'background-color',
    'rgb(40, 122, 204)',
  );
});

test('the research library supports search and card/list views', async ({
  page,
}) => {
  await page.goto('/research');
  await page.getByRole('button', { name: 'List view' }).click();
  await expect(page.getByRole('button', { name: 'List view' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await expect(page.locator('.research-cards')).toHaveClass(
    /research-cards-list/,
  );
  await page
    .getByRole('textbox', { name: 'Search research' })
    .fill('retrieval');
  await expect(page.locator('article.research-card')).toHaveCount(1);
  await expect(
    page.getByRole('heading', { name: 'Retrieval strategies', exact: true }),
  ).toBeVisible();
  await page
    .getByRole('textbox', { name: 'Search research' })
    .fill('a topic that does not exist');
  await expect(
    page.getByRole('heading', { name: 'No matching research' }),
  ).toBeVisible();
  await page.getByRole('textbox', { name: 'Search research' }).clear();
  await page.getByRole('button', { name: 'Grid view' }).click();
  await expect(page.locator('article.research-card')).toHaveCount(3);
});

test('new research starts empty and persists its own draft after refresh', async ({
  page,
}) => {
  await page.goto('/research');
  await page.getByRole('link', { name: 'New Research', exact: true }).click();
  await expect(page).toHaveURL('/research/new');
  await expect(
    page.getByRole('button', { name: 'Create research' }),
  ).toBeDisabled();
  await page
    .getByLabel('Research name', { exact: true })
    .fill('My independent research');
  await page
    .getByLabel('What are you exploring?', { exact: false })
    .fill('Investigate citation quality.');
  await page.getByRole('button', { name: 'Create research' }).click();
  await expect(page).toHaveURL(/\/research\/[a-f0-9-]{36}$/);
  const researchUrl = page.url();
  await expect(page.locator('.workspace-title')).toHaveText(
    'My independent research',
  );
  await expect(
    page.getByLabel('Research question', { exact: true }),
  ).toBeEmpty();
  await expect(
    page.getByText('Sources · 0 selected', { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'No runs yet' }),
  ).toBeVisible();
  await page
    .getByLabel('Research question', { exact: true })
    .fill('How should we measure citation quality?');
  await expect(
    page.getByRole('button', { name: 'Run Research', exact: true }),
  ).toBeDisabled();
  await page.reload();
  await expect(
    page.getByLabel('Research question', { exact: true }),
  ).toHaveValue('How should we measure citation quality?');
  await page
    .getByRole('link', { name: 'Back to all research', exact: true })
    .click();
  await page
    .getByRole('link', { name: 'Open My independent research', exact: true })
    .click();
  await expect(page).toHaveURL(researchUrl);
  await expect(
    page.getByLabel('Research question', { exact: true }),
  ).toHaveValue('How should we measure citation quality?');
  await page.getByRole('link', { name: 'Sources', exact: true }).click();
  await expect(
    page.getByRole('heading', { name: 'No sources yet' }),
  ).toBeVisible();
  await expect(
    page.getByRole('link', { name: 'architecture.pdf', exact: true }),
  ).toHaveCount(0);
});

test('switching research preserves drafts, modes, and selected sources without leaking them', async ({
  page,
}) => {
  await page.goto(transformer);
  await page
    .getByLabel('Research question', { exact: true })
    .fill('A question only for the transformer project');
  await page.getByRole('button', { name: 'Remove architecture.pdf' }).click();
  await page
    .getByRole('button', { name: 'Evidence Only', exact: true })
    .click();
  await page.getByLabel('Top-K', { exact: true }).selectOption('16');
  await page
    .getByRole('link', { name: 'Back to all research', exact: true })
    .click();
  await page
    .getByRole('link', { name: 'Open Retrieval strategies', exact: true })
    .click();
  await expect(page).toHaveURL(retrieval);
  await expect(
    page.getByLabel('Research question', { exact: true }),
  ).toHaveValue('When does hybrid retrieval outperform dense retrieval?');
  await expect(page.getByLabel('Top-K', { exact: true })).toHaveValue('8');
  await expect(
    page.getByRole('button', { name: 'Grounded Answer', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true');
  await expect(
    page.getByRole('button', { name: 'Remove retrieval-notes.pdf' }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Remove research-paper.pdf' }),
  ).toHaveCount(0);
  await expect(
    page.getByRole('heading', { name: 'No runs yet' }),
  ).toBeVisible();
  await page
    .getByRole('link', { name: 'Back to all research', exact: true })
    .click();
  await page
    .getByRole('link', { name: 'Open Transformer architectures', exact: true })
    .click();
  await expect(page).toHaveURL(transformer);
  await page.reload();
  await expect(
    page.getByLabel('Research question', { exact: true }),
  ).toHaveValue('A question only for the transformer project');
  await expect(page.getByLabel('Top-K', { exact: true })).toHaveValue('16');
  await expect(
    page.getByRole('button', { name: 'Evidence Only', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true');
  await expect(
    page.getByRole('button', { name: 'Remove architecture.pdf' }),
  ).toHaveCount(0);
  await expect(
    page.getByRole('button', { name: 'Remove research-paper.pdf' }),
  ).toBeVisible();
});

test('source selection and document inspection remain inside the active research', async ({
  page,
}) => {
  await page.goto(`${transformer}/sources`);
  await page
    .getByRole('checkbox', { name: 'Use architecture.pdf', exact: true })
    .uncheck();
  await page
    .getByRole('checkbox', { name: 'Use design-notes.docx', exact: true })
    .check();
  await expect(
    page.getByRole('checkbox', { name: 'Use retrieval-eval.pdf', exact: true }),
  ).toBeDisabled();
  await page.getByRole('link', { name: 'Research', exact: true }).click();
  await expect(
    page.getByRole('button', { name: 'Remove design-notes.docx' }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Remove architecture.pdf' }),
  ).toHaveCount(0);
  await page.getByRole('link', { name: 'Select sources', exact: true }).click();
  await page.getByPlaceholder('Filter documents...').fill('architecture');
  await expect(
    page.getByRole('link', { name: 'research-paper.pdf', exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole('link', { name: 'architecture.pdf', exact: true })
    .click();
  await expect(page).toHaveURL(`${transformer}/sources/src-001`);
  await page.getByText('Chunk 001', { exact: true }).click();
  await expect(page.getByText('chunk-001', { exact: true })).toBeVisible();
  await page
    .getByRole('button', { name: 'Content Preview', exact: true })
    .click();
  await expect(
    page.getByText('Page 1 — Document content preview', { exact: false }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByText('src-001', { exact: true })).toBeVisible();
  await page.goto(`${retrieval}/sources`);
  await expect(
    page.getByRole('link', { name: 'retrieval-notes.pdf', exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole('link', { name: 'architecture.pdf', exact: true }),
  ).toHaveCount(0);
});

test('a sample run has a scoped deep link and interactive citation evidence', async ({
  page,
}) => {
  await page.goto(transformer);
  await page
    .getByRole('link', {
      name: /How does the transformer attention mechanism differ/,
    })
    .click();
  await expect(page).toHaveURL(`${transformer}/runs/run-001`);
  await page.getByRole('button', { name: '[C1]', exact: true }).first().click();
  await expect(
    page.getByText('Evidence Inspector', { exact: true }),
  ).toBeVisible();
  await expect(page.getByText('Page 7', { exact: true })).toBeVisible();
  await expect(page.getByText('Chunk 018', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Evidence (4)', exact: true }).click();
  await expect(
    page.getByText('Encoder-only architectures use bidirectional attention', {
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Sources (3)', exact: true }).click();
  await expect(
    page.getByText('design-notes.docx', { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByText('run-001', { exact: true })).toBeVisible();
  await expect(
    page.getByText(
      'Sample result for this research · not generated from your current draft',
    ),
  ).toBeVisible();
});

test('wrong research, source, and run IDs never fall back to another research', async ({
  page,
}) => {
  await page.goto('/research/unknown-research');
  await expect(
    page.getByRole('heading', { name: 'Research not found' }),
  ).toBeVisible();
  await page.goto(`${retrieval}/sources/src-001`);
  await expect(
    page.getByRole('heading', { name: 'Source not found' }),
  ).toBeVisible();
  await expect(page.getByText('Chunk Inspector', { exact: true })).toHaveCount(
    0,
  );
  await page.goto(`${retrieval}/runs/run-001`);
  await expect(
    page.getByRole('heading', { name: 'Run not found' }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: '[C1]', exact: true }),
  ).toHaveCount(0);
  await page.goto(`${retrieval}/evidence`);
  await expect(
    page.getByText('No evidence data for this research yet.'),
  ).toBeVisible();
  await expect(page.getByText('architecture.pdf', { exact: true })).toHaveCount(
    0,
  );
  await page.goto(`${transformer}/runs/unknown-run`);
  await expect(
    page.getByRole('heading', { name: 'Run not found' }),
  ).toBeVisible();
});

test('scoped screens load and hydrate without browser errors', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  const screens = [
    ['', 'evidence-grounded research.'],
    ['/sources', 'Research Corpus'],
    ['/sources/src-001', 'Chunk Inspector'],
    ['/runs', 'Research runs'],
    ['/workflow', 'Multi-Architecture Comparison'],
    ['/evidence', 'Evidence Explorer'],
    [
      '/reports',
      'Attention Mechanism Comparison: Encoder-Only vs Decoder-Only Transformers',
    ],
    ['/graph', 'Provenance Graph'],
    ['/evaluation', 'Research Quality Metrics'],
    ['/settings', 'Workspace Name'],
  ];
  for (const [route, text] of screens) {
    const response = await page.goto(`${transformer}${route}`);
    expect(response?.status()).toBe(200);
    await expect(
      page.getByRole('main').getByText(text, { exact: true }),
    ).toBeVisible();
    await page.getByRole('button', { name: 'Search or run command' }).click();
    await expect(page.getByPlaceholder('Search commands...')).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(page.getByPlaceholder('Search commands...')).toBeHidden();
  }
  expect(errors).toEqual([]);
});

test('sidebar and command navigation preserve the research scope and browser history', async ({
  page,
}) => {
  await page.goto(transformer);
  await page.getByRole('button', { name: 'Collapse sidebar' }).click();
  await page.getByRole('link', { name: 'Sources', exact: true }).click();
  await expect(page).toHaveURL(`${transformer}/sources`);
  await expect(
    page.getByRole('button', { name: 'Expand sidebar' }),
  ).toBeVisible();
  await expect(
    page.getByRole('link', { name: 'Sources', exact: true }),
  ).toHaveAttribute('aria-current', 'page');
  await page.keyboard.press('ControlOrMeta+k');
  await page.getByPlaceholder('Search commands...').fill('Evaluation');
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(`${transformer}/evaluation`);
  await expect(
    page.getByRole('heading', { name: 'Research Quality Metrics' }),
  ).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(`${transformer}/sources`);
  await expect(
    page.getByRole('button', { name: 'Expand sidebar' }),
  ).toBeVisible();
  await page.keyboard.press('ControlOrMeta+k');
  await page.getByPlaceholder('Search commands...').fill('All research');
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL('/research');
});

test('workspace fonts and the original dark theme load in production', async ({
  page,
}) => {
  await page.goto(`${transformer}/sources`);
  await expect(
    page.getByRole('heading', { name: 'Research Corpus' }),
  ).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  const loadedFonts = await page.evaluate(() =>
    Array.from(document.fonts)
      .filter((font) => font.status === 'loaded')
      .map((font) => font.family),
  );
  expect(loadedFonts).toEqual(
    expect.arrayContaining(['Inter', 'JetBrains Mono']),
  );
  await expect(page.locator('body')).toHaveCSS(
    'background-color',
    'rgb(12, 12, 14)',
  );
});

test('landing, library, creation, and workspace work at a mobile width', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page
    .getByRole('link', { name: 'Start researching', exact: true })
    .click();
  await expect(page).toHaveURL('/research');
  await page.getByRole('link', { name: 'New Research', exact: true }).click();
  await page
    .getByLabel('Research name', { exact: true })
    .fill('Mobile research');
  await page.getByRole('button', { name: 'Create research' }).click();
  await expect(page.locator('.workspace-title')).toHaveText('Mobile research');
  await page
    .getByLabel('Research question', { exact: true })
    .fill('A question from a small screen');
  await page
    .getByRole('link', { name: 'Back to all research', exact: true })
    .click();
  await expect(page).toHaveURL('/research');
  await page
    .getByRole('link', { name: 'Open Mobile research', exact: true })
    .click();
  await expect(
    page.getByLabel('Research question', { exact: true }),
  ).toHaveValue('A question from a small screen');
  for (const route of ['/', '/research', '/research/new', transformer]) {
    await page.goto(route);
    await expect(page.getByRole('main')).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth),
    ).toBeLessThanOrEqual(390);
  }
});
