# Changelog

## Unreleased

- The monthly statement (Kontoauszug) and the annual accounts PDFs carry the club's letterhead (logo, name, address, contact line, page numbers, primary colour), the same as invoices. Hubra lays them out through `pdf.render` (hubra#332); the plugin no longer runs WeasyPrint itself, and no longer imports a private helper Hubra removed. Needs Hubra 0.2.6 or later.
- **Kontoauszug jetzt senden** needs the right to book (`finance.transactions.create`, Kassier/in) instead of the overview right, which the board's "Ansehen" has. The button is hidden without it; downloading the PDF stays with the overview right.
- A closed fiscal year keeps its annual accounts as they were when it was closed: moving a category to another account or renaming or deleting an account later no longer changes it, and the next year compares with those figures. Reopening the year drops the frozen report. Years closed before this version freeze on their first view. New table `finance_year_reports` (run `flask db upgrade`).
- A budget's owner without the right to read every budget no longer sees the club's bookings in categories outside their budget ("nicht budgetiert").
- Chart of accounts: rename and delete accounts. Budget dialogs: Abbrechen outlined, Speichern filled, Enter saves; a budget line's category can be cleared with ×; amounts without arrows.
- Dashboard widget **Geld heute**: bank and cash today, from the fiscal year's opening balances and the bookings since (needs the finance overview right).
- The dashboard widget **Budget dieses Jahr** is back. Budgets had it up to 1.3; it was lost when Finances took Budgets over. Expenses now count as positive against the plan.
- German texts of the budgets are in Standard German now; they were still in Swiss German dialect.
- Security review: creating, renaming and deleting categories, renaming an account and moving a category to another account now go into the audit log. A category planned in an approved budget can't be deleted (its budget line went with it). Amounts of 10 billion or more, payee names over 255 characters, budget texts that are too long or not text, `approved` that is not true or false, and category ids that are not whole numbers are refused with a 400 instead of a server error. A statement month outside 1900 to 2999 is a 400.
- Club databases have no foreign keys, so nothing cascaded there: deleting a category now removes its lines from open budgets itself, and a daily job clears the owner of budgets whose member was deleted (on request, for example) and lines whose category is gone.

## 1.2.0

- Gives the standard roles access when a club first switches it on (`role_defaults`, docs/roles.md in hubra-app/hubra): finance.books: Vorstand Ansehen, Kassier/in Alles; finance.budgets: Vorstand Ansehen, Kassier/in Alles. Roles without access don't see it; their own data from it stays on their profile. Needs Hubra 0.2.5 or later.

## 1.1.0

Budgets is part of Finances now. Installing or updating to 1.1.0 takes the
Budgets plugin over (`replaces: [budgets]`): its budgets and lines, the
club's module switch (Budgets stays a module of its own, `finance.budgets`,
off by default), the permission keys (`budgets.*`), the API paths
(`/api/v1/budgets`) and the fee-basis source stay as they were. Budgets
disappears from the plugin catalogue. Needs the Hubra version that knows
`replaces:` (hubra-app/hubra#272).

## 1.0.1

- Release on a pushed v* tag (works with immutable releases) (#1)
- Finances 1.0.0: the books, moved out of Hubra's Finance module (#2)
- Release: check out Hubra main again (#3)
- Talk to Hubra's Finance through contracts, not its internals (#5)

## 1.0.0

The books move out of Hubra's Finance module into this plugin: transactions,
categories, the overview and summary, recurring bookings, the monthly account
statement and the annual accounts. Same tables, API paths and permission keys
as before, so clubs keep their data and roles. Invoices book their income
here through Hubra's invoice events.
