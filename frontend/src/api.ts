// The bookkeeping API (/api/v1/app/finance/...), moved out of the club app's
// api/finance.ts. Invoices, external parties and the fee basis stay there.
import { apiFetch, apiFetchRaw } from '@hubra/plugin-sdk'
import type { Transaction, TransactionCategory } from './types'

/** Fetch up to `limit` rows of a paginated list, page by page. */
async function fetchPages<T>(path: string, params: URLSearchParams, limit: number): Promise<{ data: T[]; total: number }> {
  const pageSize = Math.min(limit, 100)
  const url = (page: number) => {
    const qs = new URLSearchParams(params)
    qs.set('page', String(page))
    qs.set('pageSize', String(pageSize))
    return `${path}?${qs}`
  }
  type Page = { data: T[]; total: number; totalPages: number }
  const first = await apiFetch<Page>(url(1))
  const pages = Math.min(first.totalPages, Math.ceil(limit / pageSize))
  const rest = await Promise.all(
    Array.from({ length: Math.max(0, pages - 1) }, (_, i) => apiFetch<Page>(url(i + 2))),
  )
  return { data: [first, ...rest].flatMap((p) => p.data).slice(0, limit), total: first.total }
}

/** Query keys; the same as the club app's, so its lists refresh too. */
export const QK = {
  transactions: ['transactions'] as const,
  recentTransactions: ['transactions', { pageSize: 5 }] as const,
  categories: ['transaction-categories'] as const,
  transaction: (id: string | undefined) => ['transactions', 'one', id] as const,
  overview: ['finance-overview'] as const,
  summary: (year: number) => ['finance-summary', year] as const,
  recurring: ['finance-recurring'] as const,
  chart: ['finance-chart'] as const,
  fiscalYears: ['finance-years'] as const,
  annualAll: ['finance-annual'] as const,
  annual: (year: number) => ['finance-annual', year] as const,
}

// ── Transaction Categories ─────────────────────────────────────────────────

interface BackendTxCategory {
  id: number;
  name: string;
  color: string | null;
  is_default: boolean;
}

function adaptTxCat(b: BackendTxCategory): TransactionCategory {
  return {
    id: String(b.id),
    name: b.name,
    color: b.color ?? "#7441e0",
    isDefault: b.is_default,
  };
}

export async function listTxCategories(): Promise<TransactionCategory[]> {
  const data = await apiFetch<BackendTxCategory[]>(
    "/app/finance/transaction-categories",
  );
  return data.map(adaptTxCat);
}

export async function createTxCategory(input: {
  name: string;
  color?: string;
}): Promise<TransactionCategory> {
  const b = await apiFetch<BackendTxCategory>(
    "/app/finance/transaction-categories",
    { method: "POST", body: JSON.stringify(input) },
  );
  return adaptTxCat(b);
}

export async function updateTxCategory(
  id: string,
  input: { name?: string; color?: string },
): Promise<TransactionCategory> {
  const b = await apiFetch<BackendTxCategory>(
    `/app/finance/transaction-categories/${id}`,
    { method: "PATCH", body: JSON.stringify(input) },
  );
  return adaptTxCat(b);
}

export async function deleteTxCategory(id: string): Promise<void> {
  await apiFetch(`/app/finance/transaction-categories/${id}`, { method: "DELETE" });
}


interface BackendTransaction {
  id: number;
  date: string;
  description: string;
  category_id: number | null;
  category_name: string | null;
  member_id: number | null;
  member_name: string | null;
  payee_name: string | null;
  amount: number;
  method: string;
  type: "income" | "expense";
  status: "Pending" | "Completed";
  invoice_id: number | null;
  created_at: string;
}

function adaptTx(b: BackendTransaction): Transaction {
  return {
    id: String(b.id),
    date: b.date,
    description: b.description,
    category: b.category_name ?? String(b.category_id ?? ""),
    member:
      b.payee_name ??
      b.member_name ??
      (b.member_id ? String(b.member_id) : "—"),
    amount: b.amount,
    method: b.method,
    type: b.type,
    status: b.status ?? "Completed",
    invoiceId: b.invoice_id != null ? String(b.invoice_id) : null,
    createdAt: b.created_at ?? "",
    categoryId: b.category_id != null ? String(b.category_id) : null,
    memberName: b.member_name,
    memberId: b.member_id != null ? String(b.member_id) : null,
    payeeName: b.payee_name,
  };
}

/** One transaction, for its detail page. */
export async function getTransaction(id: string): Promise<Transaction> {
  return adaptTx(
    await apiFetch<BackendTransaction>(`/app/finance/transactions/${id}`),
  );
}

export async function listTransactions(params?: {
  pageSize?: number;
}): Promise<Transaction[]> {
  const response = await fetchPages<BackendTransaction>(
    "/app/finance/transactions",
    new URLSearchParams(),
    params?.pageSize ?? 1000,
  );
  return response.data.map(adaptTx);
}

export interface TransactionCreate {
  date: string;
  description: string;
  categoryId?: string;
  memberId?: string;
  payeeName?: string;
  amount: number;
  method: string;
  type: "income" | "expense";
}

export async function createTransaction(
  input: TransactionCreate,
): Promise<Transaction> {
  const body: Record<string, unknown> = {
    date: input.date,
    description: input.description,
    amount: input.amount,
    method: input.method,
    type: input.type,
  };
  if (input.categoryId) body.category_id = Number(input.categoryId);
  if (input.memberId) body.member_id = Number(input.memberId);
  if (input.payeeName) body.payee_name = input.payeeName;
  const b = await apiFetch<BackendTransaction>("/app/finance/transactions", {
    method: "POST",
    body: JSON.stringify(body),
  });
  return adaptTx(b);
}

export async function updateTransaction(
  id: string,
  input: Partial<TransactionCreate> & { status?: "Pending" | "Completed" },
): Promise<Transaction> {
  const body: Record<string, unknown> = {};
  if (input.status !== undefined) body.status = input.status;
  if (input.description !== undefined) body.description = input.description;
  if (input.date !== undefined) body.date = input.date;
  if (input.amount !== undefined) body.amount = input.amount;
  if (input.method !== undefined) body.method = input.method;
  if (input.type !== undefined) body.type = input.type;
  if (input.categoryId !== undefined)
    body.category_id = input.categoryId ? Number(input.categoryId) : null;
  if (input.memberId !== undefined) body.member_id = Number(input.memberId);
  if (input.payeeName !== undefined) body.payee_name = input.payeeName;
  const b = await apiFetch<BackendTransaction>(`/app/finance/transactions/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return adaptTx(b);
}

export async function deleteTransaction(id: string): Promise<void> {
  await apiFetch(`/app/finance/transactions/${id}`, { method: "DELETE" });
}

// ── Finance Overview ───────────────────────────────────────────────────────

export interface FinanceOverview {
  balance: number;
  incomeMTD: number;
  expensesMTD: number;
  netMTD: number;
  months: { m: string; year?: number; month?: number; inc: number; exp: number }[];
  openInvoices: { count: number; amount: number };
}

export async function getFinanceOverview(): Promise<FinanceOverview> {
  return apiFetch<FinanceOverview>("/app/finance/overview");
}

export interface CategorySum {
  /** null: transactions without a category */
  id: number | null;
  name: string | null;
  color: string | null;
  income: number;
  expense: number;
  net: number;
  count: number;
}

export interface FinanceSummary {
  from: string;
  to: string;
  income: number;
  expense: number;
  net: number;
  categories: CategorySum[];
}

/** Booked income and expenses per category between two dates. */
export async function getFinanceSummary(
  from: string,
  to: string,
): Promise<FinanceSummary> {
  const qs = new URLSearchParams({ from, to });
  return apiFetch<FinanceSummary>(`/app/finance/summary?${qs}`);
}

// ── Recurring transactions ─────────────────────────────────────────────────

export type RecurringInterval = 'monthly' | 'quarterly' | 'half_yearly' | 'yearly'

export interface RecurringTransaction {
  id: number
  description: string
  type: 'income' | 'expense'
  amount: number
  categoryId: number | null
  categoryName: string
  payeeName: string | null
  method: string
  interval: RecurringInterval
  startDate: string
  endDate: string | null
  /** null once the end date has passed */
  nextDate: string | null
  bookCompleted: boolean
  countsForFees: boolean
  active: boolean
  yearlyAmount: number
}

export interface RecurringTransactionInput {
  description: string
  type: 'income' | 'expense'
  amount: number
  categoryId: number | null
  payeeName: string | null
  method: string
  interval: RecurringInterval
  startDate: string
  endDate: string | null
  bookCompleted: boolean
  countsForFees: boolean
  active: boolean
}

interface BackendRecurring {
  id: number
  description: string
  type: 'income' | 'expense'
  amount: number
  category_id: number | null
  category_name: string
  payee_name: string | null
  method: string
  interval: RecurringInterval
  start_date: string
  end_date: string | null
  next_date: string | null
  book_completed: boolean
  counts_for_fees: boolean
  active: boolean
  yearly_amount: number
}

function adaptRecurring(b: BackendRecurring): RecurringTransaction {
  return {
    id: b.id,
    description: b.description,
    type: b.type,
    amount: b.amount,
    categoryId: b.category_id,
    categoryName: b.category_name,
    payeeName: b.payee_name,
    method: b.method,
    interval: b.interval,
    startDate: b.start_date,
    endDate: b.end_date,
    nextDate: b.next_date,
    bookCompleted: b.book_completed,
    countsForFees: b.counts_for_fees,
    active: b.active,
    yearlyAmount: b.yearly_amount,
  }
}

function recurringBody(input: Partial<RecurringTransactionInput>) {
  const keys: Record<keyof RecurringTransactionInput, string> = {
    description: 'description',
    type: 'type',
    amount: 'amount',
    categoryId: 'category_id',
    payeeName: 'payee_name',
    method: 'method',
    interval: 'interval',
    startDate: 'start_date',
    endDate: 'end_date',
    bookCompleted: 'book_completed',
    countsForFees: 'counts_for_fees',
    active: 'active',
  }
  const body: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(input)) {
    body[keys[key as keyof RecurringTransactionInput]] = value
  }
  return JSON.stringify(body)
}

export async function listRecurring(): Promise<RecurringTransaction[]> {
  const data = await apiFetch<BackendRecurring[]>('/app/finance/recurring')
  return data.map(adaptRecurring)
}

export async function createRecurring(
  input: RecurringTransactionInput,
): Promise<RecurringTransaction> {
  const b = await apiFetch<BackendRecurring>('/app/finance/recurring', {
    method: 'POST',
    body: recurringBody(input),
  })
  return adaptRecurring(b)
}

export async function updateRecurring(
  id: number,
  input: Partial<RecurringTransactionInput>,
): Promise<RecurringTransaction> {
  const b = await apiFetch<BackendRecurring>(`/app/finance/recurring/${id}`, {
    method: 'PATCH',
    body: recurringBody(input),
  })
  return adaptRecurring(b)
}

export async function deleteRecurring(id: number): Promise<void> {
  await apiFetch(`/app/finance/recurring/${id}`, { method: 'DELETE' })
}

// ── Monthly account statement ──────────────────────────────────────────────

/** Downloads the account statement of a month (YYYY-MM) as a PDF. */
export async function downloadStatement(month: string): Promise<void> {
  const res = await apiFetchRaw(`/app/finance/statement.pdf?month=${month}`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `kontoauszug-${month}.pdf`
  a.click()
  URL.revokeObjectURL(url)
}

/** Mails the account statement of a month to the club's statement address. */
export async function sendStatement(month: string): Promise<{ month: string; to: string }> {
  return apiFetch('/app/finance/statement/send', {
    method: 'POST',
    body: JSON.stringify({ month }),
  })
}

// ── Yearly expenses behind percentage and formula tiers ────────────────────

export type AccountKind = 'asset' | 'liability' | 'equity' | 'income' | 'expense'

export interface Account {
  id: number
  number: string
  name: string
  kind: AccountKind
  isMoney: boolean
}

export interface Chart {
  accounts: Account[]
  categories: { id: number; name: string; accountId: number | null }[]
}

export interface AnnualLine {
  number: string
  name: string
  amount: number
  previous: number | null
}

export interface AnnualReport {
  year: number
  start: string
  end: string
  closed: boolean
  closedAt: string | null
  openingSource: 'closing' | 'computed'
  opening: { number: string; name: string; kind: AccountKind; amount: number }[]
  hasPrevious: boolean
  income: AnnualLine[]
  expense: AnnualLine[]
  totalIncome: number
  totalExpense: number
  result: number
  previousResult: number | null
  assets: AnnualLine[]
  liabilities: AnnualLine[]
  capital: { number: string; name: string; opening: number; closing: number; previous: number | null }
  totalAssets: number
  notes: {
    openInvoices: { count: number; amount: number }
    unmappedBookings: number
    pendingBookings: number
  }
}

export interface FiscalYearInfo {
  year: number
  start: string
  end: string
  closed: boolean
}

export function getChart(): Promise<Chart> {
  return apiFetch<Chart>('/app/finance/accounts')
}

export function createAccount(data: { number: string; name: string; kind: AccountKind }): Promise<Account> {
  return apiFetch<Account>('/app/finance/accounts', { method: 'POST', body: JSON.stringify(data) })
}

export function renameAccount(id: number, name: string): Promise<Account> {
  return apiFetch<Account>(`/app/finance/accounts/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ name }),
  })
}

export function deleteAccount(id: number): Promise<void> {
  return apiFetch<void>(`/app/finance/accounts/${id}`, { method: 'DELETE' })
}

export function mapCategoryAccount(categoryId: number, accountId: number | null): Promise<unknown> {
  return apiFetch(`/app/finance/accounts/categories/${categoryId}`, {
    method: 'PUT',
    body: JSON.stringify({ accountId }),
  })
}

export function listFiscalYears(): Promise<{ years: FiscalYearInfo[]; startMonth: number }> {
  return apiFetch('/app/finance/annual')
}

export function getAnnualReport(year: number): Promise<AnnualReport> {
  return apiFetch<AnnualReport>(`/app/finance/annual/${year}`)
}

export function setOpeningBalances(year: number, balances: Record<string, number>): Promise<AnnualReport> {
  return apiFetch<AnnualReport>(`/app/finance/annual/${year}/opening`, {
    method: 'PUT',
    body: JSON.stringify({ balances }),
  })
}

export function closeFiscalYear(year: number): Promise<AnnualReport> {
  return apiFetch<AnnualReport>(`/app/finance/annual/${year}/close`, { method: 'POST' })
}

export function reopenFiscalYear(year: number): Promise<AnnualReport> {
  return apiFetch<AnnualReport>(`/app/finance/annual/${year}/reopen`, { method: 'POST' })
}

export async function downloadAnnualAccounts(year: number, lang: string): Promise<void> {
  const res = await apiFetchRaw(`/app/finance/annual/${year}.pdf?lang=${lang}`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `jahresrechnung-${year}.pdf`
  a.click()
  URL.revokeObjectURL(url)
}
