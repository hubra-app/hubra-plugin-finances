"""A right on invoices is not a right on the books: the plugin's routes
keep Finance's keys, one per resource (finance.transactions.*)."""



def test_finance_invoices_read_does_not_grant_transactions_read(
    client, seeded_db, permissioned_member_factory, db
):
    """A user with finance.invoices.read must NOT access finance.transactions.read."""
    headers = permissioned_member_factory(["finance.invoices.read"])

    # transactions list — should be 403
    resp = client.get("/api/v1/finance/transactions", headers=headers)
    assert resp.status_code == 403


def test_finance_invoices_create_does_not_grant_transactions_create(
    client, seeded_db, permissioned_member_factory
):
    """A user with finance.invoices.create must NOT create transactions."""
    headers = permissioned_member_factory(["finance.invoices.create"])
    resp = client.post(
        "/api/v1/finance/transactions",
        json={
            "amount": 100,
            "category_id": 1,
            "date": "2026-01-01",
            "type": "expense",
        },
        headers=headers,
    )
    assert resp.status_code == 403
