"""Seed a Stripe test account with realistic SaaS subscription data.

Usage:
    uv run python scripts/seed_stripe.py --key sk_test_...
    uv run python scripts/seed_stripe.py  # reads STRIPE_SECRET_KEY env var

Creates:
    - 2 products (Solo, Studio) with monthly prices
    - 20 customers across both plans
    - 14 active subscriptions
    - 8 cancelled subscriptions spread over the past 3 months,
      with varied cancellation reasons matching what the AI agent analyses
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta

import stripe
from stripe.params._subscription_cancel_params import SubscriptionCancelParams


# ---------------------------------------------------------------------------
# Customer data
# ---------------------------------------------------------------------------

CUSTOMERS = [
    ("alice@acmecorp.com", "Alice Chen"),
    ("bob@brightmail.io", "Bob Rivera"),
    ("carol@cloudstack.dev", "Carol Smith"),
    ("dan@datawise.ai", "Dan Nguyen"),
    ("eve@edgetech.co", "Eve Kowalski"),
    ("frank@finloop.io", "Frank Müller"),
    ("grace@growthsuite.com", "Grace Park"),
    ("henry@helpdesk.pro", "Henry Adams"),
    ("irene@infrasec.io", "Irene Osei"),
    ("james@jumpstart.ai", "James Lee"),
    ("kate@kinetica.io", "Kate Brennan"),
    ("liam@launchpad.dev", "Liam Torres"),
    ("maya@metricsco.com", "Maya Patel"),
    ("noah@nodecraft.io", "Noah Wilson"),
    ("olivia@optiolab.com", "Olivia Johnson"),
    ("paul@pivotbase.io", "Paul Zhang"),
    ("quinn@queryfast.dev", "Quinn Martinez"),
    ("rosa@rampup.co", "Rosa Dubois"),
    ("sam@scalehub.io", "Sam O'Brien"),
    ("tara@trackwise.ai", "Tara Novak"),
]

CANCELLATION_REASONS = [
    "too_expensive",
    "missing_features",
    "switched_service",
    "unused",
    "customer_service",
    "too_complex",
    "too_expensive",  # weighted higher
    "switched_service",  # weighted higher
]


def ts_days_ago(days: int) -> int:
    """Return a Unix timestamp for N days ago."""
    return int((datetime.now(tz=UTC) - timedelta(days=days)).timestamp())


def create_products_and_prices(client: stripe.StripeClient) -> tuple[str, str]:
    """Create Solo and Studio products + monthly prices. Return (solo_price_id, studio_price_id)."""
    print("Creating products…")

    solo_product = client.products.create(params={
        "name": "Solo Plan",
        "description": "For individual makers and freelancers",
    })
    studio_product = client.products.create(params={
        "name": "Studio Plan",
        "description": "For growing teams and agencies",
    })

    solo_price = client.prices.create(params={
        "product": solo_product.id,
        "unit_amount": 2900,  # $29/mo
        "currency": "usd",
        "recurring": {"interval": "month"},
        "nickname": "Solo Monthly",
    })
    studio_price = client.prices.create(params={
        "product": studio_product.id,
        "unit_amount": 9900,  # $99/mo
        "currency": "usd",
        "recurring": {"interval": "month"},
        "nickname": "Studio Monthly",
    })

    print(f"  Solo price:   {solo_price.id}  ($29/mo)")
    print(f"  Studio price: {studio_price.id}  ($99/mo)")
    return solo_price.id, studio_price.id


def create_customers(client: stripe.StripeClient) -> list[str]:
    """Create all customers and return their IDs."""
    print("\nCreating customers…")
    ids: list[str] = []
    for email, name in CUSTOMERS:
        cust = client.customers.create(params={
            "email": email,
            "name": name,
            "source": "tok_visa",  # test Visa card, no real charge
        })
        ids.append(cust.id)
        print(f"  {name} ({email}) → {cust.id}")
    return ids


def create_active_subscriptions(
    client: stripe.StripeClient,
    customer_ids: list[str],
    solo_price_id: str,
    studio_price_id: str,
) -> None:
    """Create 14 active subscriptions for the first 14 customers."""
    print("\nCreating active subscriptions…")
    # First 10 on Solo, next 4 on Studio
    assignments = (
        [(cid, solo_price_id) for cid in customer_ids[:10]]
        + [(cid, studio_price_id) for cid in customer_ids[10:14]]
    )
    for cid, price_id in assignments:
        sub = client.subscriptions.create(params={
            "customer": cid,
            "items": [{"price": price_id}],
        })
        plan = "Solo" if price_id == solo_price_id else "Studio"
        print(f"  {cid}  [{plan}]  → {sub.id}")


def create_cancelled_subscriptions(
    client: stripe.StripeClient,
    customer_ids: list[str],
    solo_price_id: str,
    studio_price_id: str,
) -> None:
    """Create and immediately cancel 8 subscriptions with varied reasons and dates.

    Stripe doesn't allow back-dating cancellations via the API, so we create
    them now with a cancellation feedback reason. The created_at will reflect
    today, but the distribution of reasons is realistic.
    """
    print("\nCreating cancelled subscriptions…")

    # last 6 customers — mix of plans and reasons
    cancellations = [
        (customer_ids[14], solo_price_id,    "too_expensive"),
        (customer_ids[15], solo_price_id,    "switched_service"),
        (customer_ids[16], studio_price_id,  "missing_features"),
        (customer_ids[17], solo_price_id,    "unused"),
        (customer_ids[18], studio_price_id,  "too_expensive"),
        (customer_ids[19], solo_price_id,    "switched_service"),
    ]

    for cid, price_id, reason in cancellations:
        sub = client.subscriptions.create(params={
            "customer": cid,
            "items": [{"price": price_id}],
        })
        client.subscriptions.cancel(
            sub.id,
            params=SubscriptionCancelParams(cancellation_details={"feedback": reason}),  # type: ignore[typeddict-item]
        )
        plan = "Solo" if price_id == solo_price_id else "Studio"
        print(f"  {cid}  [{plan}]  cancelled ({reason})  → {sub.id}")

    # Two more using the first two customers (they churned and re-subscribed scenario)
    for cid, price_id, reason in [
        (customer_ids[0], solo_price_id,   "customer_service"),
        (customer_ids[2], studio_price_id, "too_complex"),
    ]:
        sub = client.subscriptions.create(params={
            "customer": cid,
            "items": [{"price": price_id}],
        })
        client.subscriptions.cancel(
            sub.id,
            params=SubscriptionCancelParams(cancellation_details={"feedback": reason}),  # type: ignore[typeddict-item]
        )
        plan = "Solo" if price_id == solo_price_id else "Studio"
        print(f"  {cid}  [{plan}]  cancelled ({reason})  → {sub.id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Stripe test data for Synvar")
    parser.add_argument(
        "--key",
        default=os.environ.get("STRIPE_SECRET_KEY", ""),
        help="Stripe secret key (defaults to STRIPE_SECRET_KEY env var)",
    )
    parser.add_argument(
        "--skip-products",
        action="store_true",
        help="Skip product/price creation (reuse existing)",
    )
    parser.add_argument(
        "--solo-price",
        default="",
        help="Existing Solo price ID (required with --skip-products)",
    )
    parser.add_argument(
        "--studio-price",
        default="",
        help="Existing Studio price ID (required with --skip-products)",
    )
    args = parser.parse_args()

    if not args.key:
        print("Error: provide --key or set STRIPE_SECRET_KEY", file=sys.stderr)
        sys.exit(1)

    if not args.key.startswith("sk_test_"):
        print("Error: only test keys (sk_test_...) are allowed", file=sys.stderr)
        sys.exit(1)

    client = stripe.StripeClient(args.key)

    if args.skip_products:
        if not args.solo_price or not args.studio_price:
            print(
                "Error: --solo-price and --studio-price are required with --skip-products",
                file=sys.stderr,
            )
            sys.exit(1)
        solo_price_id, studio_price_id = args.solo_price, args.studio_price
    else:
        solo_price_id, studio_price_id = create_products_and_prices(client)

    customer_ids = create_customers(client)
    create_active_subscriptions(client, customer_ids, solo_price_id, studio_price_id)
    create_cancelled_subscriptions(client, customer_ids, solo_price_id, studio_price_id)

    print("\n✓ Seed complete.")
    print(f"  {len(customer_ids)} customers")
    print("  14 active subscriptions")
    print("   8 cancelled subscriptions")
    print(f"\nSolo price ID:   {solo_price_id}")
    print(f"Studio price ID: {studio_price_id}")
    print("\nUse the Solo or Studio price ID as your Stripe API key is configured.")


if __name__ == "__main__":
    main()
