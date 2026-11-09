# Finances

The club's books for [Hubra](https://hubra.club): transactions and their
categories, the overview with this month's figures and the last twelve
months, recurring bookings, the monthly account statement and the annual
accounts (Jahresrechnung) with a chart of accounts.

Invoices, reminders, the Swiss QR-bill, membership fees, the fee basis and
external parties stay in Hubra's Finance module. With this plugin on, every
invoice books its income here, and paying the invoice completes the booking.

**Plugin id** `finances` · **Package** `hubra_finances` · **Modules** `finance.books`, `finance.budgets` (need `finance`) · **Works with** Hubra `>=0.2,<1`

## Coming from Hubra's built-in books

These pages were part of Hubra's Finance module up to 0.x. Nothing moves in
the database: the tables, the API paths (`/api/v1/app/finance/...`) and the
permission keys (`finance.transactions.*`, `finance.overview.read`,
`finance.accounts.*`, ...) stay the same, so clubs keep their books and
roles keep their rights.

After deploying the Hubra version without the built-in books, install
**Finances** from the catalogue (Manage › Plugins). The module is on by
default for every club that has Finance on. Until then, Finanzen shows only
the invoices, the fee basis and the settings, and new invoices are not
booked.

## Coming from the Budgets plugin

Budgets (a yearly plan per category, compared with the bookings) was a
plugin of its own up to 1.3. Finances 1.1 took it over: installing or
updating Finances removes the Budgets plugin from the platform and keeps
everything it had, the `budgets` and `budget_lines` tables, each club's
Budgets switch, the `budgets.*` permission keys and the API paths. Budgets
stays its own module, so a club that doesn't plan keeps it off.

## What it adds

| Where | What |
| --- | --- |
| Finanzen › Übersicht | balance, this month, the last twelve months, sums per category |
| Finanzen › Buchungen | income and expenses, each with its own page; recurring bookings |
| Finanzen › Budget | a budget per year and category, planned against booked; approve, lock, copy to next year (module `finance.budgets`) |
| Finanzen › Jahresrechnung | the annual accounts, opening balances, closing a year |
| Finanzen › Einstellungen | transaction categories; the monthly statement card under Abrechnung |
| Fee basis | the sources "recurring expenses", "last year's expenses" and "budget" |
| Search (Ctrl+K) | transactions |
| Jobs | due recurring bookings every day; the statement on the first of the month |

## Develop

Clone it into `plugins/finances` of a Hubra checkout, then from
`app/backend` run `pytest ../../plugins/finances`, and from `app/frontend`
`npm run typecheck:plugins` and `npm run build:plugin -- ../../plugins/finances`.
The browser specs in `e2e/` run from Hubra's `app/frontend/e2e`.

## Release

Push a tag that matches `plugin.yaml` (`git tag v1.0.0 && git push origin v1.0.0`).
The workflow tests, signs (environment `plugin-signing`) and publishes the
release with `finances-<version>.zip`. See `.github/workflows/release.yml`.

License: AGPL-3.0-or-later.
