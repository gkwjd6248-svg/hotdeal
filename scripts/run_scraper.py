"""Manual scraper runner for testing and debugging adapters.

This script allows you to run specific shop adapters manually to test
their functionality and see the deals they fetch in real-time.

Usage:
    python scripts/run_scraper.py --shop naver
    python scripts/run_scraper.py --shop naver --category pc-hardware
    python scripts/run_scraper.py --shop naver --limit 5
"""

import asyncio
import argparse
import sys
import os
from decimal import Decimal

# Add backend to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.scrapers.adapters.naver import NaverShoppingAdapter

# Registry of available adapters
ADAPTERS = {
    "naver": NaverShoppingAdapter,
}


async def run_scraper(shop_slug: str, category: str = None, limit: int = 10):
    """Run a scraper adapter and display the results.

    Args:
        shop_slug: The shop slug (e.g., "naver", "coupang")
        category: Optional category filter (e.g., "pc-hardware")
        limit: Maximum number of deals to display (default: 10)
    """
    # Check if adapter exists
    adapter_cls = ADAPTERS.get(shop_slug)
    if not adapter_cls:
        print(f"\n❌ Error: Unknown shop '{shop_slug}'")
        print(f"\n📋 Available shops:")
        for slug in sorted(ADAPTERS.keys()):
            print(f"   - {slug}")
        return

    print(f"\n{'='*70}")
    print(f"  Running {shop_slug.upper()} Scraper")
    print(f"{'='*70}")

    if category:
        print(f"  🏷️  Category: {category}")
    print(f"  📊 Display Limit: {limit}")
    print(f"{'='*70}\n")

    # Initialize adapter
    adapter = adapter_cls()
    print(f"✅ Initialized {adapter.shop_name} adapter")
    print(f"   Type: {adapter.adapter_type}")
    print(f"   Slug: {adapter.shop_slug}\n")

    try:
        # Fetch deals
        print(f"🔍 Fetching deals...\n")
        deals = await adapter.fetch_deals(category=category)

        if not deals:
            print("⚠️  No deals found.\n")
            return

        print(f"✅ Found {len(deals)} deals\n")
        print(f"{'='*70}")
        print(f"  Top {min(limit, len(deals))} Deals")
        print(f"{'='*70}\n")

        # Display deals
        for i, deal in enumerate(deals[:limit], 1):
            print(f"[{i}] {deal.title}")
            print(f"    💰 Price: {_format_price(deal.deal_price, deal.product.currency)}")

            if deal.original_price:
                print(f"    🔖 Original: {_format_price(deal.original_price, deal.product.currency)}")

            if deal.discount_percentage:
                print(f"    📉 Discount: {deal.discount_percentage}%")

            print(f"    🏷️  Type: {deal.deal_type}")

            if deal.product.brand:
                print(f"    🏢 Brand: {deal.product.brand}")

            if deal.product.category_hint:
                print(f"    📁 Category: {deal.product.category_hint}")

            print(f"    🔗 URL: {deal.deal_url[:80]}...")
            print()

        # Summary
        print(f"{'='*70}")
        print(f"  Summary")
        print(f"{'='*70}")
        print(f"  Total Deals: {len(deals)}")
        print(f"  Displayed: {min(limit, len(deals))}")

        # Calculate average discount
        deals_with_discount = [d for d in deals if d.discount_percentage]
        if deals_with_discount:
            avg_discount = sum(d.discount_percentage for d in deals_with_discount) / len(deals_with_discount)
            print(f"  Avg Discount: {avg_discount:.1f}%")

        # Count by deal type
        deal_types = {}
        for deal in deals:
            deal_types[deal.deal_type] = deal_types.get(deal.deal_type, 0) + 1

        print(f"  Deal Types:")
        for deal_type, count in sorted(deal_types.items()):
            print(f"    - {deal_type}: {count}")

        print(f"{'='*70}\n")

    except Exception as e:
        print(f"\n❌ Error occurred while fetching deals:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        print(f"\n📋 Full traceback:")
        traceback.print_exc()
        print()

    finally:
        # Cleanup
        if hasattr(adapter, "cleanup"):
            await adapter.cleanup()
            print("🧹 Cleaned up adapter resources\n")


def _format_price(price: Decimal, currency: str) -> str:
    """Format price with currency symbol.

    Args:
        price: The price value
        currency: Currency code (e.g., "KRW", "USD")

    Returns:
        Formatted price string
    """
    if currency == "KRW":
        return f"{price:,.0f}원"
    elif currency == "USD":
        return f"${price:,.2f}"
    elif currency == "CNY":
        return f"¥{price:,.2f}"
    else:
        return f"{price:,.2f} {currency}"


def main():
    """Parse arguments and run the scraper."""
    parser = argparse.ArgumentParser(
        description="Run a shop scraper adapter for testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_scraper.py --shop naver
  python scripts/run_scraper.py --shop naver --category pc-hardware
  python scripts/run_scraper.py --shop naver --limit 5
        """,
    )

    parser.add_argument(
        "--shop",
        required=True,
        help="Shop slug (e.g., 'naver', 'coupang')",
    )

    parser.add_argument(
        "--category",
        help="Optional category filter (e.g., 'pc-hardware', 'laptop-mobile')",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of deals to display (default: 10)",
    )

    args = parser.parse_args()

    # Run the scraper
    asyncio.run(run_scraper(args.shop, args.category, args.limit))


if __name__ == "__main__":
    main()
