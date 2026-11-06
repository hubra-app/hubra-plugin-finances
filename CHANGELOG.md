# Changelog

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
