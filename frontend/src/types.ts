// Bookkeeping types, as the club app's src/types had them.
export interface TransactionCategory {
  id: string;
  name: string;
  color: string;
  isDefault: boolean;
}

export interface Transaction {
  id: string;
  date: string;
  description: string;
  category: string;
  member: string;
  amount: number;
  method: string;
  type: "income" | "expense";
  status: "Pending" | "Completed";
  invoiceId: string | null;
  createdAt: string;
  categoryId?: string | null;
  memberName?: string | null;
  memberId?: string | null;
  payeeName?: string | null;
}
