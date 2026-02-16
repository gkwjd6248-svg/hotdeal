#!/usr/bin/env python3
"""Verification script for Phase 4 scraper adapters.

This script verifies that all scraper adapters can be imported
and that they are properly registered with the adapter factory.
"""

import sys


def verify_imports():
    """Verify all scraper adapters can be imported."""
    print("=" * 80)
    print("Phase 4 Verification: Scraper Adapter Imports")
    print("=" * 80)
    print()

    adapters_to_test = [
        ("gmarket", "GmarketAdapter"),
        ("auction", "AuctionAdapter"),
        ("ssg", "SSGAdapter"),
        ("himart", "HimartAdapter"),
        ("lotteon", "LotteonAdapter"),
        ("interpark", "InterparkAdapter"),
        ("musinsa", "MusinsaAdapter"),
        ("ssf", "SSFAdapter"),
    ]

    failed = []

    for module_name, class_name in adapters_to_test:
        try:
            module = __import__(
                f"app.scrapers.adapters.{module_name}",
                fromlist=[class_name]
            )
            adapter_class = getattr(module, class_name)

            # Verify it has the required attributes
            assert hasattr(adapter_class, "shop_slug"), f"{class_name} missing shop_slug"
            assert hasattr(adapter_class, "shop_name"), f"{class_name} missing shop_name"
            assert hasattr(adapter_class, "adapter_type"), f"{class_name} missing adapter_type"
            assert adapter_class.adapter_type == "scraper", f"{class_name} wrong adapter_type"

            print(f"✓ {class_name:20s} - {adapter_class.shop_slug:12s} ({adapter_class.shop_name})")

        except Exception as e:
            print(f"✗ {class_name:20s} - FAILED: {e}")
            failed.append((module_name, str(e)))

    print()

    if failed:
        print(f"FAILED: {len(failed)} adapter(s) could not be imported")
        for module_name, error in failed:
            print(f"  - {module_name}: {error}")
        return False
    else:
        print(f"SUCCESS: All {len(adapters_to_test)} scraper adapters imported successfully")
        return True


def verify_factory_registration():
    """Verify all adapters are registered with the factory."""
    print()
    print("=" * 80)
    print("Phase 4 Verification: Adapter Factory Registration")
    print("=" * 80)
    print()

    try:
        from app.scrapers.register_adapters import register_all_adapters
        from app.scrapers.factory import get_adapter_factory

        # Register all adapters
        register_all_adapters()
        factory = get_adapter_factory()

        # Get registered shops
        registered_shops = factory.get_registered_shops()
        print(f"Total registered adapters: {len(registered_shops)}")
        print()

        # Expected scraper adapters
        expected_scrapers = [
            "gmarket", "auction", "ssg", "himart",
            "lotteon", "interpark", "musinsa", "ssf"
        ]

        # Verify each scraper is registered
        missing = []
        for shop_slug in expected_scrapers:
            if factory.has_adapter(shop_slug):
                adapter = factory.create_adapter(shop_slug)
                print(f"✓ {shop_slug:12s} - {adapter.shop_name} ({adapter.adapter_type})")
            else:
                print(f"✗ {shop_slug:12s} - NOT REGISTERED")
                missing.append(shop_slug)

        print()

        if missing:
            print(f"FAILED: {len(missing)} adapter(s) not registered")
            return False
        else:
            print(f"SUCCESS: All {len(expected_scrapers)} scraper adapters registered")
            return True

    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_base_classes():
    """Verify base class inheritance."""
    print()
    print("=" * 80)
    print("Phase 4 Verification: Base Class Inheritance")
    print("=" * 80)
    print()

    try:
        from app.scrapers.base import BaseScraperAdapter
        from app.scrapers.adapters import (
            GmarketAdapter, AuctionAdapter, SSGAdapter, HimartAdapter,
            LotteonAdapter, InterparkAdapter, MusinsaAdapter, SSFAdapter
        )

        adapters = [
            GmarketAdapter, AuctionAdapter, SSGAdapter, HimartAdapter,
            LotteonAdapter, InterparkAdapter, MusinsaAdapter, SSFAdapter
        ]

        failed = []
        for adapter_class in adapters:
            if issubclass(adapter_class, BaseScraperAdapter):
                print(f"✓ {adapter_class.__name__:20s} - inherits from BaseScraperAdapter")
            else:
                print(f"✗ {adapter_class.__name__:20s} - DOES NOT inherit from BaseScraperAdapter")
                failed.append(adapter_class.__name__)

        print()

        if failed:
            print(f"FAILED: {len(failed)} adapter(s) have incorrect inheritance")
            return False
        else:
            print(f"SUCCESS: All {len(adapters)} adapters inherit from BaseScraperAdapter")
            return True

    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all verification tests."""
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "PHASE 4 VERIFICATION SUITE" + " " * 32 + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    results = []

    # Test 1: Import verification
    results.append(("Import Test", verify_imports()))

    # Test 2: Factory registration
    results.append(("Factory Registration", verify_factory_registration()))

    # Test 3: Base class inheritance
    results.append(("Base Class Inheritance", verify_base_classes()))

    # Summary
    print()
    print("=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    print()

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "PASS ✓" if result else "FAIL ✗"
        print(f"{test_name:30s} - {status}")

    print()
    print(f"Total: {passed}/{total} tests passed")
    print()

    if passed == total:
        print("🎉 ALL TESTS PASSED - Phase 4 is complete and verified!")
        return 0
    else:
        print(f"⚠️  {total - passed} test(s) failed - please review errors above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
