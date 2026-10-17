import { expect, test, type Page } from '@playwright/test';

async function startAssessment(page: Page, topics: string[], length: 'Quick' | 'Standard' | 'Extended') {
  await page.goto('/start');
  await page.getByRole('button', { name: 'Clear all' }).click();
  for (const topic of topics) await page.getByRole('checkbox', { name: new RegExp(topic) }).check();
  await page.getByRole('radio', { name: new RegExp(length) }).check();
  await page.getByRole('button', { name: 'Start assessment' }).click();
  await expect(page).toHaveURL(/\/assessment\/[0-9a-f]{32}$/);
  await expect(page.locator('.progress-meta')).toContainText('Question 1');
}

async function answerCurrent(page: Page, optionIndex = 0) {
  await page.locator('.option').nth(optionIndex).click();
  await page.getByRole('button', { name: 'Submit answer' }).click();
  await expect(page.getByRole('heading', { name: /Correct|Not quite/ })).toBeVisible();
}

async function finishAssessment(page: Page) {
  for (let i = 0; i < 25; i += 1) {
    await answerCurrent(page);
    const seeResults = page.getByRole('button', { name: 'See my results' });
    if (await seeResults.isVisible()) {
      await seeResults.click();
      break;
    }
    await page.getByRole('button', { name: 'Next question' }).click();
  }
  await expect(page).toHaveURL(/\/results\/[0-9a-f]{32}$/);
}

test('complete diagnostic: setup, adaptive questions, results, study plan, history', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('GRE preparation');
  await page.getByRole('link', { name: 'Start a diagnostic' }).click();
  await expect(page.getByRole('heading', { name: 'Set up your diagnostic' })).toBeVisible();

  await startAssessment(page, ['Algebra', 'Vocabulary'], 'Quick');

  // Answer key and difficulty are never shown before answering.
  const html = await page.content();
  expect(html).not.toContain('answer_index');
  expect(html).not.toMatch(/difficulty/i);

  await answerCurrent(page, 1);
  await expect(page.locator('.option-correct')).toHaveCount(1);
  await page.getByRole('button', { name: 'Next question' }).click();
  await expect(page.locator('.progress-meta')).toContainText('Question 2');

  await finishAssessment(page);

  await expect(page.getByRole('heading', { name: 'Your results' })).toBeVisible();
  await expect(page.locator('.band-label')).toHaveText(/Foundational|Developing|Proficient|Advanced/);
  await expect(page.getByRole('table', { name: /Results by topic/ })).toContainText('Algebra');
  await expect(page.getByRole('img', { name: /Ability estimate after each answer/ })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Download JSON' })).toHaveAttribute('href', /\/export$/);

  // AI-generated when a provider is configured, rule-based otherwise; either must render.
  await page.getByRole('button', { name: 'Generate study plan' }).click();
  await expect(page.locator('#plan-heading + .badge')).toHaveText(/AI-generated|Rule-based/, {
    timeout: 45_000,
  });
  const evidence = page.locator('.plan-step a[href^="#question-"]').first();
  if (await evidence.count()) {
    const target = (await evidence.getAttribute('href'))!.slice(1);
    await page.getByRole('button', { name: /^Correct \(/ }).click(); // hide incorrect items first
    await evidence.click();
    await expect(page.locator(`#${target}`)).toHaveAttribute('open', '');
  }

  // Review filter works.
  await page.getByRole('button', { name: /^Incorrect \(/ }).click();
  await expect(page.locator('.review-item .badge-success')).toHaveCount(0);

  const resultsUrl = page.url().split('#')[0]!;
  await page.getByRole('link', { name: 'History' }).click();
  await expect(page.getByRole('heading', { name: 'Assessment history' })).toBeVisible();
  await expect(page.getByText('Completed').first()).toBeVisible();
  await page.getByRole('link', { name: 'View results' }).first().click();
  await expect(page).toHaveURL(resultsUrl);
});

test('a slow double submit sends exactly one answer', async ({ page }) => {
  await startAssessment(page, ['Geometry'], 'Quick');
  let posts = 0;
  await page.route('**/answers', async (route) => {
    posts += 1;
    await new Promise((resolve) => setTimeout(resolve, 800));
    await route.continue();
  });
  await page.locator('.option').first().click();
  const submit = page.getByRole('button', { name: 'Submit answer' });
  await submit.click();
  await expect(page.getByRole('button', { name: 'Submitting...' })).toBeDisabled();
  await page
    .getByRole('button', { name: 'Submitting...' })
    .click({ force: true })
    .catch(() => undefined);
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: /Correct|Not quite/ })).toBeVisible();
  expect(posts).toBe(1);
});

test('a network failure during submission can be retried without losing progress', async ({ page }) => {
  await startAssessment(page, ['Data Analysis'], 'Quick');
  let failed = false;
  await page.route('**/answers', async (route) => {
    if (!failed) {
      failed = true;
      await route.abort('internetdisconnected');
    } else {
      await route.continue();
    }
  });
  await page.locator('.option').first().click();
  await page.getByRole('button', { name: 'Submit answer' }).click();
  await expect(page.getByRole('alert')).toContainText('Could not reach the server');
  await page.getByRole('button', { name: 'Try again' }).click();
  await expect(page.getByRole('heading', { name: /Correct|Not quite/ })).toBeVisible();
});

test('reloading mid-assessment resumes at the same question', async ({ page }) => {
  await startAssessment(page, ['Arithmetic'], 'Quick');
  await answerCurrent(page);
  await page.getByRole('button', { name: 'Next question' }).click();
  const stem = await page.locator('.question-stem').textContent();
  await page.reload();
  await expect(page.locator('.progress-meta')).toContainText('Question 2');
  await expect(page.locator('.question-stem')).toHaveText(stem!);
});

test('keyboard only: select with arrows and submit with Enter', async ({ page }) => {
  await startAssessment(page, ['Vocabulary'], 'Quick');
  const first = page.getByRole('radio').first();
  await first.focus();
  await page.keyboard.press('Space');
  await page.keyboard.press('ArrowDown');
  await expect(page.getByRole('radio').nth(1)).toBeChecked();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: /Correct|Not quite/ })).toBeFocused();
});

test('setup validation, unknown assessments, and unknown pages', async ({ page }) => {
  await page.goto('/start');
  await page.getByRole('button', { name: 'Clear all' }).click();
  await page.getByRole('button', { name: 'Start assessment' }).click();
  await expect(page.getByRole('alert')).toHaveText('Select at least one topic.');

  await page.goto(`/assessment/${'a'.repeat(32)}`);
  await expect(page.getByRole('heading', { name: 'Assessment not found' })).toBeVisible();
  await page.goto('/results/not-an-id');
  await expect(page.getByRole('heading', { name: 'Results not found' })).toBeVisible();
  await page.goto('/no/such/page');
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible();
});

test('clearing history asks for confirmation', async ({ page }) => {
  await startAssessment(page, ['Algebra'], 'Quick');
  await page.goto('/history');
  await expect(page.getByText('In progress')).toBeVisible();
  await page.getByRole('button', { name: 'Clear history' }).click();
  await page.getByRole('button', { name: 'Cancel' }).click();
  await expect(page.getByText('In progress')).toBeVisible();
  await page.getByRole('button', { name: 'Clear history' }).click();
  await page.getByRole('button', { name: 'Remove all' }).click();
  await expect(page.getByRole('heading', { name: 'No assessments yet' })).toBeVisible();
});

test('@responsive pages fit small screens without horizontal scrolling', async ({ page }) => {
  for (const path of ['/', '/start', '/history']) {
    await page.goto(path);
    await expect(page.locator('main h1')).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow, `horizontal overflow on ${path}`).toBeLessThanOrEqual(0);
  }
  await startAssessment(page, ['Geometry'], 'Quick');
  await finishAssessment(page);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, 'horizontal overflow on results').toBeLessThanOrEqual(0);
});
