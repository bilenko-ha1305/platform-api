"""Delete all test customers, subscriptions, and products from a Stripe test account.

Usage:
    uv run python scripts/clear_stripe.py --key sk_test_...
    uv run python scripts/clear_stripe.py  # reads STRIPE_SECRET_KEY env var

Only works with test keys (sk_test_...). Iterates through all customers,
cancels their subscriptions, then deletes them. Then deletes all products.
"""

from __future__ import annotations

import argparse
import os
import sys

import stripe


def cancel_and_delete_customers(client: stripe.StripeClient) -> int:
    """Cancel all subscriptions and delete all customers. Returns count."""
    count = 0
    has_more = True
    starting_after: str | None = None

    while has_more:
        params: dict[str, object] = {"limit": 100}
        if starting_after:
            params["starting_after"] = starting_after

        page = client.customers.list(params=params)  # type: ignore[arg-type]
        customers = page.data

        for cust in customers:
            # Cancel active subscriptions first
            subs = client.subscriptions.list(params={"customer": cust.id, "status": "active"})
            for sub in subs.data:
                client.subscriptions.cancel(sub.id)

            client.customers.delete(cust.id)
            print(f"  Deleted customer {cust.id} ({getattr(cust, 'email', '')})")
            count += 1

        has_more = page.has_more
        if customers:
            starting_after = customers[-1].id

    return count


def delete_products(client: stripe.StripeClient) -> int:
    """Archive all products (Stripe doesn't allow hard-deletion of products with prices)."""
    count = 0
    has_more = True
    starting_after: str | None = None

    while has_more:
        params: dict[str, object] = {"limit": 100, "active": True}
        if starting_after:
            params["starting_after"] = starting_after

        page = client.products.list(params=params)  # type: ignore[arg-type]
        products = page.data

        for prod in products:
            # Archive prices first, then the product
            prices = client.prices.list(params={"product": prod.id, "active": True})
            for price in prices.data:
                client.prices.update(price.id, params={"active": False})

            client.products.update(prod.id, params={"active": False})
            print(f"  Archived product {prod.id} ({getattr(prod, 'name', '')})")
            count += 1

        has_more = page.has_more
        if products:
            starting_after = products[-1].id

    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clear all Stripe test data for Revelio"
    )
    parser.add_argument(
        "--key",
        default=os.environ.get("STRIPE_SECRET_KEY", ""),
        help="Stripe secret key (defaults to STRIPE_SECRET_KEY env var)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt",
    )
    args = parser.parse_args()

    if not args.key:
        print("Error: provide --key or set STRIPE_SECRET_KEY", file=sys.stderr)
        sys.exit(1)

    if not args.key.startswith("sk_test_"):
        print("Error: only test keys (sk_test_...) are allowed", file=sys.stderr)
        sys.exit(1)

    if not args.yes:
        confirm = input(
            "This will DELETE all customers and archive all products in the test account.\n"
            "Type 'yes' to continue: "
        )
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            sys.exit(0)

    client = stripe.StripeClient(args.key)

    print("\nDeleting customers and subscriptions…")
    cust_count = cancel_and_delete_customers(client)

    print("\nArchiving products and prices…")
    prod_count = delete_products(client)

    print(f"\n✓ Cleared {cust_count} customers and {prod_count} products.")


if __name__ == "__main__":
    main()
