import { expect, test } from '@playwright/test';
import type { Job, Research, Result } from '../src/data/research';

const cases = [
  { status: 'completed', outcome: 'completed', label: 'completed' },
  { status: 'completed_with_gaps', outcome: 'completed', label: 'Completed — gaps noted' },
  {
    status: 'completed_with_gaps',
    outcome: 'insufficient_context',
    label: 'Finished — insufficient evidence',
  },
] as const;

for (const { status, outcome, label } of cases) {
  test(`outcome presentation: ${label}`, async ({ page }) => {
    const projectId = '11111111-1111-4111-8111-111111111111';
    const jobId = '22222222-2222-4222-8222-222222222222';
    const timestamp = '2026-09-26T00:00:00Z';
    const question = 'What do the selected sources establish?';
    const insufficient = outcome === 'insufficient_context';
    const project: Research = {
      id: projectId,
      title: 'Outcome presentation fixture',
      description: '',
      updated_at: timestamp,
      sources: [],
      draft: {
        question: '',
        mode: 'agentic',
        source_ids: [],
        web_urls: [],
        top_k: 4,
        retrieval_strategy: 'hybrid',
      },
      runs: [
        {
          id: jobId,
          question,
          mode: 'agentic',
          status,
          outcome,
          created_at: timestamp,
          completed_at: timestamp,
        },
      ],
    };
    const job: Job = {
      job_id: jobId,
      workspace_id: projectId,
      run_id: jobId,
      question,
      mode: 'agentic',
      retrieval_strategy: 'hybrid',
      status,
      outcome,
      progress: {
        total_tasks: 4,
        succeeded_tasks: 4,
        failed_tasks: 0,
        cancelled_tasks: 0,
        skipped_tasks: 0,
      },
      budget: {
        used_provider_calls: 3,
        max_provider_calls: 20,
        used_input_tokens: 200,
        used_output_tokens: 100,
        reserved_input_tokens: 0,
        reserved_output_tokens: 0,
      },
      policy: { allow_web: false, allowed_domains: [], web_urls: [] },
      created_at: timestamp,
      started_at: timestamp,
      completed_at: timestamp,
      error: null,
    };
    const result: Result = {
      job_id: jobId,
      workspace_id: projectId,
      run_id: jobId,
      result_id: jobId,
      status,
      outcome,
      mode: 'agentic',
      question,
      summary: 'Fixture summary for checking status presentation.',
      limitation: insufficient
        ? 'The selected evidence does not establish deployment status.'
        : null,
      claims: [],
      evidence: [],
      citations: [],
      source_coverage: [],
      contradictions: [],
      task_failures: [],
      external_sources: [],
      gaps:
        status === 'completed_with_gaps'
          ? [
              {
                gap_id: jobId,
                text: 'Deployment status is not established.',
                reason: 'no_evidence',
              },
            ]
          : [],
      model: null,
      prompt_version: 'fixture',
      budget: job.budget,
      usage: {
        duration_ms: 100,
        retrieval_ms: 10,
        synthesis_ms: 50,
        input_tokens: 200,
        output_tokens: 100,
        embedding_tokens: 10,
      },
      review: null,
    };
    // Isolate presentation from model variability; API integration tests cover saved outcomes.
    const responses: Record<string, unknown> = {
      '/v1/projects': { projects: [project], total: 1 },
      [`/v1/projects/${projectId}`]: project,
      [`/v1/research/jobs/${jobId}`]: job,
      [`/v1/research/jobs/${jobId}/result`]: result,
      [`/v1/research/jobs/${jobId}/tasks`]: { tasks: [] },
      [`/v1/research/jobs/${jobId}/plan`]: { status: 'validated' },
      [`/v1/research/jobs/${jobId}/events`]: { events: [], next_cursor: 0, has_more: false },
      [`/v1/projects/${projectId}/evaluation`]: {
        job_count: 1,
        statuses: { [status]: 1 },
        rejected_plans: 0,
        provider_calls: 3,
        input_tokens: 200,
        output_tokens: 100,
        unknown_usage_calls: 0,
        review_count: 0,
        human_scores: {},
        note: 'Fixture execution statistics.',
        runs: [
          {
            job_id: jobId,
            question,
            status,
            outcome,
            mode: 'agentic',
            duration_ms: 100,
            provider_calls: 3,
            reviewed: false,
          },
        ],
      },
    };
    await page.route('**/api/backend/v1/**', async (route) => {
      const path = new URL(route.request().url()).pathname.replace('/api/backend', '');
      expect(responses[path], `Unexpected API request: ${path}`).toBeDefined();
      await route.fulfill({ json: responses[path] });
    });
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    const base = `/research/${projectId}`;

    await page.goto(base + '/runs');
    await expect(page.locator('.run-card .state-badge')).toHaveText(label);
    await page.locator('.run-card').click();
    await expect(page.locator('.run-page > .page-heading .state-badge')).toHaveText(label);
    await page.getByRole('tab', { name: 'Plan & execution', exact: true }).click();
    await expect(page.locator('.job-monitor > .page-heading')).toContainText(label);
    await expect(page.getByRole('button', { name: 'Cancel run' })).toHaveCount(0);
    if (status === 'completed_with_gaps') {
      await expect(page.locator('.job-monitor > .warning-notice')).toContainText(
        insufficient ? 'evidence was insufficient' : 'produced a result with recorded limitations',
      );
    }
    await page.getByRole('tab', { name: 'Result', exact: true }).click();
    if (insufficient) {
      await expect(page.locator('.result-content > .warning-notice')).toContainText(
        'Insufficient evidence for an answer',
      );
    }
    if (result.gaps.length) {
      await page.getByRole('tab', { name: 'Gaps (1)', exact: true }).click();
      await expect(
        page.getByText('Deployment status is not established.', { exact: true }),
      ).toBeVisible();
    }

    await page.goto(base + '/reports');
    await expect(page.locator('.report-document > .state-badge')).toHaveText(label);
    await page.goto(base + '/evaluation');
    await expect(page.locator('tbody .state-badge')).toHaveText(label);
    const outcomes = page.locator('.metric').filter({ hasText: 'Results / insufficient evidence' });
    await expect(outcomes.locator('strong')).toHaveText(insufficient ? '0 / 1' : '1 / 0');

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(base + '/runs/' + jobId);
    await expect(page.locator('.run-page > .page-heading .state-badge')).toHaveText(label);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      390,
    );
    expect(errors).toEqual([]);
  });
}
