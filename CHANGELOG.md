# Changelog

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
