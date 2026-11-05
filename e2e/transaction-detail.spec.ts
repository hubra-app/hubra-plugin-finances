import { expect, test, type Page } from '@playwright/test'
import { api, enableModule, unique } from './api'
import { appUrl } from './env'

// A transaction opens as its own page (like a member), not in a side panel:
// a deep link works, the back link returns to the list, and the edit dialog
// opens from the page.

const main = (page: Page) => page.getByRole('main')

test('a transaction opens as its own page from the list', async ({ page }) => {
  await page.goto(appUrl('finance/transactions'))
  await enableModule(page, 'finance')
  const description = unique('E2E Buchung')
  const tx = await api<{ id: number }>(page, 'POST', '/finance/transactions', {
    date: new Date().toISOString().slice(0, 10),
    description,
    amount: 42.5,
    method: 'Cash',
    type: 'expense',
  })
  try {
    await page.goto(appUrl('finance/transactions'))
    await main(page).getByText(description).first().click()
    await expect(page).toHaveURL(new RegExp(`/app/finance/transactions/${tx.id}$`))
    await expect(main(page).getByRole('heading', { level: 1, name: description })).toBeVisible()
    await expect(page.getByTestId('transaction-amount')).toContainText('42.50')

    await main(page).getByRole('button', { name: 'Bearbeiten' }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await page.getByRole('dialog').getByRole('button', { name: 'Abbrechen' }).click()
    await expect(page.getByRole('dialog')).toBeHidden()

    // Old ?tx= links land on the page too.
    await page.goto(appUrl(`finance/transactions?tx=${tx.id}`))
    await expect(page).toHaveURL(new RegExp(`/app/finance/transactions/${tx.id}$`))

    // Deleting from the page goes back to the list.
    await page.goto(appUrl(`finance/transactions/${tx.id}`))
    await expect(main(page).getByRole('heading', { level: 1, name: description })).toBeVisible()
    await main(page).getByRole('button', { name: 'Löschen' }).click()
    await page.getByRole('dialog').getByRole('button', { name: 'Löschen' }).click()
    await expect(page).toHaveURL(/\/app\/finance\/transactions$/)
  } catch (err) {
    await api(page, 'DELETE', `/finance/transactions/${tx.id}`).catch(() => {})
    throw err
  }
})
