"""Quick test script to verify Naver adapter syntax and basic functionality."""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

try:
    from app.scrapers.adapters.naver import NaverShoppingAdapter
    print("✓ NaverShoppingAdapter imported successfully")

    # Test instantiation
    adapter = NaverShoppingAdapter()
    print(f"✓ Adapter instantiated: {adapter.shop_name} ({adapter.shop_slug})")
    print(f"  Adapter type: {adapter.adapter_type}")

    # Test static methods
    test_html = "<b>테스트</b> 제품 &amp; 특가"
    cleaned = adapter._strip_html(test_html)
    print(f"✓ HTML stripping works: '{test_html}' → '{cleaned}'")

    print("\n✓ All basic checks passed!")
    print("\nNote: To test API calls, set NAVER_CLIENT_ID and NAVER_CLIENT_SECRET in .env")

except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
