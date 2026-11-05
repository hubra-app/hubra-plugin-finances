import { categoryColors, colorText, registerPlugin } from '@hubra/plugin-sdk'
import { listTransactions } from './api'
import { AnnualAccountsTab } from './AnnualAccountsTab'
import { FinanceOverviewTab } from './FinanceOverviewTab'
import { RecurringTab } from './RecurringTab'
import { StatementCard } from './StatementCard'
import { TransactionCategoriesTab } from './TransactionCategoriesTab'
import { TransactionDetailScreen } from './TransactionDetail'
import { TransactionsTab } from './TransactionsTab'
import translations from './translations.json'

const MODULE = 'finance.books'

// The pages of Finanzen that keep the books. Their addresses stay as they
// were in the club app (/app/finance, /app/finance/transactions, ...).
registerPlugin({
  id: 'finances',
  tabs: [
    { screen: 'finance', group: 'overview', id: 'overview', label: 'shell.nav.overview', module: MODULE, order: 10, component: FinanceOverviewTab },
    { screen: 'finance', group: 'bookings', id: 'transactions', label: 'shell.nav.incomeExpenses', module: MODULE, perm: 'finance.transactions.read', order: 10, component: TransactionsTab },
    { screen: 'finance', group: 'bookings', id: 'recurring', label: 'shell.nav.recurring', module: MODULE, perm: 'finance.transactions.read', order: 20, component: RecurringTab },
    { screen: 'finance', group: 'annual', id: 'annual', label: 'shell.nav.annualAccounts', module: MODULE, perm: 'finance.accounts.read', order: 10, component: AnnualAccountsTab },
    { screen: 'finance', group: 'setup', id: 'categories', label: 'shell.nav.txCategories', module: MODULE, perm: 'finance.transaction_categories.read', order: 10, component: TransactionCategoriesTab },
  ],
  routes: [
    { path: 'finance/transactions/:id', module: MODULE, perm: 'finance.transactions.read', component: TransactionDetailScreen },
  ],
  slots: [
    { slot: 'finance.settings', module: MODULE, component: StatementCard },
  ],
  search: [
    {
      id: 'transactions',
      label: 'shell.searchKind.transaction',
      color: {
        bg: `color-mix(in srgb, ${categoryColors.blue} 12%, var(--hb-surface))`,
        color: colorText(categoryColors.blue),
      },
      module: MODULE,
      perm: 'finance.transactions.read',
      load: async () =>
        (await listTransactions({ pageSize: 200 })).map((tx) => ({
          id: tx.id,
          label: tx.description,
          sub: `${tx.type} · CHF ${tx.amount}`,
          path: `/app/finance/transactions/${tx.id}`,
          keywords: [tx.category, tx.member].filter(Boolean).join(' '),
        })),
    },
  ],
  translations,
})
