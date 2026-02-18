"""Local scraper runner script for DealHawk.

Runs Playwright-based scraper adapters on the local PC and sends results
to the remote backend via POST API. Intended for Windows development machines
that can run Playwright while the backend is hosted on Render.

Usage:
    # Scrape all browser-based shops
    python local_scraper.py --api-key YOUR_KEY

    # Scrape a specific shop
    python local_scraper.py --shop gmarket --api-key YOUR_KEY

    # Dry run (scrape but do not POST to backend)
    python local_scraper.py --shop gmarket --api-key YOUR_KEY --dry-run

    # Custom backend URL (e.g. local dev server)
    python local_scraper.py --shop gmarket --api-key YOUR_KEY --backend-url http://localhost:8000

Setup (run once):
    pip install -r requirements-local.txt
    playwright install chromium
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Graceful import guards -- give clear errors before anything else fails
# ---------------------------------------------------------------------------
try:
    import httpx
except ImportError:
    print("[오류] httpx가 설치되어 있지 않습니다.")
    print("       pip install -r requirements-local.txt  을 실행하세요.")
    sys.exit(1)

try:
    import structlog
except ImportError:
    print("[오류] structlog가 설치되어 있지 않습니다.")
    print("       pip install -r requirements-local.txt  을 실행하세요.")
    sys.exit(1)

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext
except ImportError:
    print("[오류] playwright가 설치되어 있지 않습니다.")
    print("       pip install playwright && playwright install chromium  을 실행하세요.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Local sys.path fix so `app.*` imports resolve when running from backend/
# ---------------------------------------------------------------------------
import os

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

# ---------------------------------------------------------------------------
# Adapter imports  (must come after sys.path fix)
# ---------------------------------------------------------------------------
try:
    from app.scrapers.base import NormalizedDeal
    from app.scrapers.utils.rate_limiter import DomainRateLimiter
    from app.scrapers.utils.user_agents import get_random_user_agent

    # Playwright-based scraper adapters
    from app.scrapers.adapters.gmarket import GmarketAdapter
    from app.scrapers.adapters.auction import AuctionAdapter
    from app.scrapers.adapters.ssg import SSGAdapter
    from app.scrapers.adapters.himart import HimartAdapter
    from app.scrapers.adapters.lotteon import LotteonAdapter
    from app.scrapers.adapters.musinsa import MusinsaAdapter
    from app.scrapers.adapters.ssf import SSFAdapter
    from app.scrapers.adapters.taobao import TaobaoAdapter
except ImportError as exc:
    print(f"[오류] 어댑터 임포트 실패: {exc}")
    print("       backend/ 디렉터리에서 실행하고 있는지 확인하세요.")
    print("       예: cd backend && python local_scraper.py ...")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Logging setup — force UTF-8 stdout for non-ASCII (Chinese, emoji, etc.)
# ---------------------------------------------------------------------------
import io as _io

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = _io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True,
    )
    sys.stderr = _io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True,
    )

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="%H:%M:%S"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

log = structlog.get_logger("local_scraper")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_BACKEND_URL = "https://hotdeal.onrender.com"
INGEST_ENDPOINT = "/api/v1/ingest/deals"

# Map of shop slug -> adapter class for browser-based shops
BROWSER_SHOP_REGISTRY: Dict[str, Any] = {
    "gmarket": GmarketAdapter,
    "auction": AuctionAdapter,
    "ssg": SSGAdapter,
    "himart": HimartAdapter,
    "lotteon": LotteonAdapter,
    # interpark: 여행/엔터테인먼트로 전환됨 (nol.interpark.com), 쇼핑 상품 없음
    "musinsa": MusinsaAdapter,
    "ssf": SSFAdapter,
    "taobao": TaobaoAdapter,
}

# Stealth JS injected into every browser context
_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko', 'en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = { runtime: {} };
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) =>
  parameters.name === 'notifications'
    ? Promise.resolve({ state: Notification.permission })
    : originalQuery(parameters);
"""


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def _decimal_default(obj: Any) -> Any:
    """JSON serializer for Decimal and datetime types."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def deal_to_dict(deal: NormalizedDeal) -> Dict[str, Any]:
    """Convert a NormalizedDeal dataclass to a JSON-serialisable dict.

    Args:
        deal: NormalizedDeal instance returned by an adapter.

    Returns:
        Plain dict suitable for JSON serialisation.
    """
    return {
        "external_id": deal.product.external_id,
        "title": deal.title,
        "deal_price": float(deal.deal_price),
        "original_price": float(deal.original_price) if deal.original_price else None,
        "discount_percentage": (
            float(deal.discount_percentage) if deal.discount_percentage else None
        ),
        "deal_url": deal.deal_url,
        "image_url": deal.image_url,
        "category_hint": deal.product.category_hint,
        "deal_type": deal.deal_type,
        "brand": deal.product.brand,
        "description": deal.description,
        "starts_at": deal.starts_at.isoformat() if deal.starts_at else None,
        "expires_at": deal.expires_at.isoformat() if deal.expires_at else None,
        "metadata": deal.metadata or {},
    }


# ---------------------------------------------------------------------------
# Browser context factory
# ---------------------------------------------------------------------------


async def _create_browser_context(
    browser: Browser,
    block_images: bool = True,
) -> BrowserContext:
    """Create an anti-detection browser context.

    Args:
        browser: Launched Playwright Browser instance.
        block_images: Whether to block image/font requests for speed.

    Returns:
        Configured BrowserContext.
    """
    context = await browser.new_context(
        user_agent=get_random_user_agent(),
        viewport={"width": 1920, "height": 1080},
        locale="ko-KR",
        timezone_id="Asia/Seoul",
        java_script_enabled=True,
        bypass_csp=True,
    )

    # Inject navigator stealth patches
    await context.add_init_script(_STEALTH_JS)

    # Block heavy resources to speed up scraping
    if block_images:
        await context.route(
            "**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,eot}",
            lambda route: route.abort(),
        )

    return context


# ---------------------------------------------------------------------------
# Backend posting
# ---------------------------------------------------------------------------


async def post_deals_to_backend(
    deals: List[Dict[str, Any]],
    shop_slug: str,
    backend_url: str,
    api_key: str,
    http_client: httpx.AsyncClient,
) -> Dict[str, Any]:
    """POST scraped deals to the backend ingest endpoint.

    The backend expects IngestRequest JSON:
      {
        "api_key": "<key>",
        "shop_slug": "<slug>",
        "deals": [...]
      }

    On success the backend returns IngestResponse:
      {
        "status": "success",
        "stats": {
          "received": N,
          "products_created": N,
          "products_updated": N,
          "deals_created": N,
          "deals_skipped": N,
          "errors": N
        }
      }

    Args:
        deals: List of deal dicts (output of deal_to_dict).
        shop_slug: Shop identifier (e.g. "gmarket").
        backend_url: Backend base URL (e.g. "https://hotdeal.onrender.com").
        api_key: API key — sent in the JSON body as ``api_key``.
        http_client: Shared httpx AsyncClient.

    Returns:
        Dict with keys "sent", "accepted", "rejected", "error".
    """
    url = backend_url.rstrip("/") + INGEST_ENDPOINT

    # Payload matches IngestRequest schema in app/schemas/ingest.py
    payload = {
        "api_key": api_key,
        "shop_slug": shop_slug,
        "deals": deals,
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = await http_client.post(
            url,
            content=json.dumps(payload, default=_decimal_default),
            headers=headers,
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        # Parse IngestResponse.stats
        stats = data.get("stats", {})
        accepted = stats.get("deals_created", 0) + stats.get("products_created", 0)
        rejected = stats.get("deals_skipped", 0) + stats.get("errors", 0)
        return {
            "sent": len(deals),
            "accepted": accepted,
            "rejected": rejected,
            "error": None,
            "stats": stats,
        }
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:300]
        return {
            "sent": len(deals),
            "accepted": 0,
            "rejected": len(deals),
            "error": f"HTTP {exc.response.status_code}: {body}",
        }
    except Exception as exc:
        return {
            "sent": len(deals),
            "accepted": 0,
            "rejected": len(deals),
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Per-shop scrape runner
# ---------------------------------------------------------------------------


@dataclass
class ShopResult:
    """Summary of a scraping run for a single shop."""

    shop_slug: str
    deals_found: int
    deals_sent: int
    deals_accepted: int
    deals_rejected: int
    elapsed_seconds: float
    error: Optional[str] = None


async def scrape_shop(
    shop_slug: str,
    adapter_class: Any,
    browser: Browser,
    rate_limiter: DomainRateLimiter,
    backend_url: str,
    api_key: str,
    http_client: httpx.AsyncClient,
    dry_run: bool = False,
) -> ShopResult:
    """Scrape a single shop and optionally POST results to the backend.

    Args:
        shop_slug: Shop identifier (e.g. "gmarket").
        adapter_class: Scraper adapter class to instantiate.
        browser: Shared Playwright Browser instance.
        rate_limiter: Shared DomainRateLimiter instance.
        backend_url: Backend base URL.
        api_key: API key for authentication.
        http_client: Shared httpx AsyncClient.
        dry_run: If True, scrape but do not POST to backend.

    Returns:
        ShopResult summary.
    """
    start_time = time.monotonic()
    print(f"\n[{shop_slug}] 스크래핑 시작...")

    # Create a fresh browser context per shop for isolation
    context = await _create_browser_context(browser)

    try:
        # Instantiate adapter and inject dependencies
        adapter = adapter_class()
        adapter.rate_limiter = rate_limiter
        adapter.browser_context = context

        # Fetch deals
        deals: List[NormalizedDeal] = await adapter.fetch_deals()
        print(f"[{shop_slug}] {len(deals)}개 딜 발견")

        if not deals:
            return ShopResult(
                shop_slug=shop_slug,
                deals_found=0,
                deals_sent=0,
                deals_accepted=0,
                deals_rejected=0,
                elapsed_seconds=time.monotonic() - start_time,
            )

        # Convert to dicts
        deal_dicts = []
        for deal in deals:
            try:
                deal_dicts.append(deal_to_dict(deal))
            except Exception as exc:
                log.warning("deal_conversion_failed", shop=shop_slug, error=str(exc))

        # Dry run: print samples and return
        if dry_run:
            def _safe(s: str) -> str:
                """Encode string safely for Windows cp949 console output."""
                return s.replace('\xa0', ' ').encode('cp949', 'replace').decode('cp949')

            print(f"[{shop_slug}] [DRY RUN] 백엔드 전송 건너뜀. 딜 {len(deal_dicts)}개:")
            for i, sample in enumerate(deal_dicts[:5]):
                orig = sample.get('original_price')
                pct = sample.get('discount_percentage')
                title = _safe(sample.get('title', 'N/A'))[:60]
                price_str = f"     가격: {sample.get('deal_price', 0):,.0f}원"
                if orig and pct:
                    price_str += f" (원래 {orig:,.0f}원, -{pct:.0f}%)"
                print(f"  {i+1}. {title}")
                print(price_str)
            if len(deal_dicts) > 5:
                print(f"  ... 외 {len(deal_dicts)-5}개")
            return ShopResult(
                shop_slug=shop_slug,
                deals_found=len(deals),
                deals_sent=0,
                deals_accepted=0,
                deals_rejected=0,
                elapsed_seconds=time.monotonic() - start_time,
            )

        # POST to backend
        print(f"[{shop_slug}] 백엔드에 {len(deal_dicts)}개 딜 전송 중...")
        result = await post_deals_to_backend(
            deals=deal_dicts,
            shop_slug=shop_slug,
            backend_url=backend_url,
            api_key=api_key,
            http_client=http_client,
        )

        if result["error"]:
            print(f"[{shop_slug}] 전송 오류: {result['error']}")
        else:
            stats = result.get("stats", {})
            print(
                f"[{shop_slug}] 전송 완료: "
                f"상품생성={stats.get('products_created', 0)}개 "
                f"상품갱신={stats.get('products_updated', 0)}개 "
                f"딜생성={stats.get('deals_created', 0)}개 "
                f"딜건너뜀={stats.get('deals_skipped', 0)}개 "
                f"오류={stats.get('errors', 0)}개"
            )

        return ShopResult(
            shop_slug=shop_slug,
            deals_found=len(deals),
            deals_sent=result["sent"],
            deals_accepted=result["accepted"],
            deals_rejected=result["rejected"],
            elapsed_seconds=time.monotonic() - start_time,
            error=result["error"],
        )

    except Exception as exc:
        elapsed = time.monotonic() - start_time
        log.error("shop_scrape_failed", shop=shop_slug, error=str(exc))
        print(f"[{shop_slug}] 스크래핑 실패: {exc}")
        return ShopResult(
            shop_slug=shop_slug,
            deals_found=0,
            deals_sent=0,
            deals_accepted=0,
            deals_rejected=0,
            elapsed_seconds=elapsed,
            error=str(exc),
        )

    finally:
        # Always close the per-shop context
        try:
            await context.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------


def print_summary(results: List[ShopResult], dry_run: bool) -> None:
    """Print a formatted summary table of all scraping results.

    Args:
        results: List of ShopResult objects.
        dry_run: Whether this was a dry run.
    """
    mode_label = "[DRY RUN] " if dry_run else ""
    print("\n" + "=" * 60)
    print(f"  {mode_label}스크래핑 결과 요약")
    print("=" * 60)
    print(f"{'쇼핑몰':<12} {'발견':>6} {'전송':>6} {'수락':>6} {'거절':>6} {'시간':>8}  상태")
    print("-" * 60)

    total_found = total_sent = total_accepted = total_rejected = 0

    for r in results:
        status = "성공" if not r.error else "오류"
        print(
            f"{r.shop_slug:<12} "
            f"{r.deals_found:>6} "
            f"{r.deals_sent:>6} "
            f"{r.deals_accepted:>6} "
            f"{r.deals_rejected:>6} "
            f"{r.elapsed_seconds:>7.1f}s  "
            f"{status}"
        )
        total_found += r.deals_found
        total_sent += r.deals_sent
        total_accepted += r.deals_accepted
        total_rejected += r.deals_rejected

    print("-" * 60)
    print(
        f"{'합계':<12} "
        f"{total_found:>6} "
        f"{total_sent:>6} "
        f"{total_accepted:>6} "
        f"{total_rejected:>6}"
    )
    print("=" * 60)

    # Print errors for failed shops
    errors = [(r.shop_slug, r.error) for r in results if r.error]
    if errors:
        print("\n[오류 상세]")
        for slug, err in errors:
            print(f"  {slug}: {err}")


# ---------------------------------------------------------------------------
# Playwright browser check / install helper
# ---------------------------------------------------------------------------


def ensure_playwright_browsers() -> None:
    """Check that Chromium is installed and print help if not.

    Playwright raises a meaningful error at launch time if the browser binary
    is missing, so this function is advisory only — it prints an early,
    human-readable message before the async event loop starts so the user
    does not have to wait through Python startup to see the error.

    Detection strategy: ask Playwright to list installed browsers (``show``
    command available since 1.x). If the output does not mention chromium,
    print the install command and continue (Playwright will fail loudly later).
    """
    import subprocess

    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # If playwright itself is missing this will raise FileNotFoundError or
        # return a non-zero exit. In both cases we skip the check and let the
        # import guard at the top of the file handle it.
        if result.returncode != 0:
            return
    except Exception:
        return

    # Attempt a quick executable presence check using the Python playwright API
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            # get_browser_path returns the expected path; if it doesn't exist
            # the browser has not been installed.
            chromium_path = p.chromium.executable_path
            if not os.path.exists(chromium_path):
                print("[경고] Chromium 브라우저가 설치되어 있지 않습니다.")
                print("       다음 명령어로 설치하세요:")
                print("         playwright install chromium")
                print()
    except Exception:
        # Any failure here is non-fatal; Playwright's own launch() error is
        # descriptive enough.
        pass


# ---------------------------------------------------------------------------
# Main async entrypoint
# ---------------------------------------------------------------------------


async def main(
    shops: List[str],
    backend_url: str,
    api_key: str,
    dry_run: bool,
    headless: bool,
) -> None:
    """Main async runner.

    Args:
        shops: List of shop slugs to scrape.
        backend_url: Backend base URL.
        api_key: API key for backend authentication.
        dry_run: If True, scrape but do not POST.
        headless: Whether to run Chromium in headless mode.
    """
    print("\nDealHawk 로컬 스크래퍼 시작")
    print(f"  대상 쇼핑몰: {', '.join(shops)}")
    print(f"  백엔드 URL : {backend_url}")
    print(f"  모드       : {'DRY RUN (전송 안 함)' if dry_run else '실제 전송'}")
    print(f"  헤드리스   : {headless}")
    print()

    rate_limiter = DomainRateLimiter()
    results: List[ShopResult] = []

    async with async_playwright() as playwright:
        print("[브라우저] Chromium 실행 중...")
        browser = await playwright.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        print("[브라우저] Chromium 실행 완료\n")

        async with httpx.AsyncClient(timeout=60.0) as http_client:
            for shop_slug in shops:
                adapter_class = BROWSER_SHOP_REGISTRY.get(shop_slug)
                if adapter_class is None:
                    print(f"[{shop_slug}] 알 수 없는 쇼핑몰 — 건너뜀")
                    continue

                result = await scrape_shop(
                    shop_slug=shop_slug,
                    adapter_class=adapter_class,
                    browser=browser,
                    rate_limiter=rate_limiter,
                    backend_url=backend_url,
                    api_key=api_key,
                    http_client=http_client,
                    dry_run=dry_run,
                )
                results.append(result)

        print("\n[브라우저] 종료 중...")
        await browser.close()

    print_summary(results, dry_run=dry_run)


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed Namespace object.
    """
    parser = argparse.ArgumentParser(
        description="DealHawk 로컬 스크래퍼 — Playwright로 쇼핑몰을 스크래핑하고 결과를 백엔드에 전송합니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 모든 쇼핑몰 스크래핑 (실제 전송)
  python local_scraper.py --api-key YOUR_KEY

  # 특정 쇼핑몰만
  python local_scraper.py --shop gmarket --api-key YOUR_KEY

  # 드라이런 (전송 안 함)
  python local_scraper.py --shop gmarket --api-key YOUR_KEY --dry-run

  # 여러 쇼핑몰
  python local_scraper.py --shop gmarket --shop auction --api-key YOUR_KEY

  # 로컬 백엔드
  python local_scraper.py --backend-url http://localhost:8000 --api-key dev
        """,
    )

    parser.add_argument(
        "--shop",
        action="append",
        dest="shops",
        metavar="SHOP_SLUG",
        help=(
            "스크래핑할 쇼핑몰 슬러그 (여러 번 지정 가능). "
            f"선택: {', '.join(sorted(BROWSER_SHOP_REGISTRY.keys()))}. "
            "지정하지 않으면 모든 쇼핑몰을 스크래핑합니다."
        ),
    )

    parser.add_argument(
        "--api-key",
        required=False,
        default="",
        help="백엔드 인증 API 키. --dry-run 시 불필요.",
    )

    parser.add_argument(
        "--backend-url",
        default=DEFAULT_BACKEND_URL,
        help=f"백엔드 베이스 URL (기본값: {DEFAULT_BACKEND_URL})",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="스크래핑은 하되 백엔드에 전송하지 않습니다 (테스트용).",
    )

    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="브라우저 창을 표시합니다 (디버깅용). 기본값은 headless.",
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = parse_args()

    # Determine shop list
    if args.shops:
        target_shops = args.shops
    else:
        target_shops = list(BROWSER_SHOP_REGISTRY.keys())

    # Validate shop slugs early
    unknown = [s for s in target_shops if s not in BROWSER_SHOP_REGISTRY]
    if unknown:
        print(f"[오류] 알 수 없는 쇼핑몰: {', '.join(unknown)}")
        print(f"       유효한 쇼핑몰: {', '.join(sorted(BROWSER_SHOP_REGISTRY.keys()))}")
        sys.exit(1)

    # API key is required unless dry run
    if not args.dry_run and not args.api_key:
        print("[오류] --api-key 가 필요합니다 (또는 --dry-run 을 사용하세요).")
        sys.exit(1)

    # Pre-check Playwright browsers
    ensure_playwright_browsers()

    # Run
    try:
        asyncio.run(
            main(
                shops=target_shops,
                backend_url=args.backend_url,
                api_key=args.api_key,
                dry_run=args.dry_run,
                headless=not args.no_headless,
            )
        )
    except KeyboardInterrupt:
        print("\n\n[중단] 사용자에 의해 중단되었습니다.")
        sys.exit(0)
