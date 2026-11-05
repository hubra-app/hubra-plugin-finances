import { expect, test } from '@playwright/test'
import { appUrl } from './env'

const tabNames = async (page: import('@playwright/test').Page, row?: string) => {
  const scope = row ? page.getByRole('tablist', { name: row, exact: true }) : page
  await expect(scope.getByRole('tab').first()).toBeVisible()
  return (await scope.getByRole('tab').allInnerTexts()).map((s) => s.trim())
}

test('finance has five page tabs, with sub-tabs where a topic has several lists', async ({
  page,
}) => {
  await page.goto(appUrl('finance'))
  await expect(page.getByRole('tab', { name: 'Übersicht' })).toBeVisible()
  const names = await tabNames(page, 'Finanzen')
  expect(names.slice(0, 3)).toEqual(['Übersicht', 'Rechnungen', 'Buchungen'])
  // "Budget & Beiträge" with the budgets plugin, else just the fee basis.
  expect(['Budget & Beiträge', 'Beitragsgrundlage']).toContain(names[3])
  expect(names.at(-1)).toBe('Einstellungen')
  // The overview has no second row.
  await expect(page.getByRole('tablist')).toHaveCount(1)

  await page.getByRole('tab', { name: 'Buchungen' }).click()
  await expect(page).toHaveURL(/\/app\/finance\/transactions$/)
  const bookings = await tabNames(page, 'Buchungen')
  expect(bookings.slice(0, 2)).toEqual(['Einnahmen und Ausgaben', 'Wiederkehrend'])
  await page.getByRole('tab', { name: 'Wiederkehrend' }).click()
  await expect(page).toHaveURL(/\/app\/finance\/recurring$/)
  await expect(page.getByRole('tab', { name: 'Buchungen' })).toHaveAttribute('aria-selected', 'true')

  await page.getByRole('tab', { name: 'Einstellungen' }).click()
  await expect(page).toHaveURL(/\/app\/finance\/settings$/)
  expect(await tabNames(page, 'Einstellungen')).toEqual([
    'Abrechnung',
    'Kategorien',
    'Externe Parteien',
    'Bank & QR-Rechnung',
  ])
})

test('old finance addresses open their page under the new tab', async ({ page }) => {
  for (const [path, tab, sub] of [
    ['finance/categories', 'Einstellungen', 'Kategorien'],
    ['finance/external-parties', 'Einstellungen', 'Externe Parteien'],
    ['finance/recurring', 'Buchungen', 'Wiederkehrend'],
  ] as const) {
    await page.goto(appUrl(path))
    await expect(page.getByRole('tab', { name: tab, exact: true })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    await expect(page.getByRole('tab', { name: sub, exact: true })).toHaveAttribute(
      'aria-selected',
      'true',
    )
  }
})
