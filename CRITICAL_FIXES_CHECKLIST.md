# DealHawk Phase 1 - Critical Fixes Checklist

## Must-Fix Before Any Testing or Deployment

Use this checklist to track fixes for all critical and high-severity issues.

---

## CRITICAL ISSUES (3)

### CRITICAL-1: Schema Field Naming - `size` vs `limit`
**Status:** [ ] Not Started [ ] In Progress [ ] Fixed [ ] Tested

**Files to Update:**
- [ ] `backend/app/schemas/common.py` - Line 14: Confirm field name is `limit`
- [ ] `frontend/lib/types.ts` - Line 15: Change `size: number` to `limit: number`
- [ ] Verify all API clients handle the renamed field

**Verification:**
```bash
# After fix, test pagination:
curl "http://localhost:8000/api/v1/deals?page=1&limit=20"
# Should return pagination meta with 'limit' field, not 'size'
```

**Impact:** BLOCKS all pagination functionality

---

### CRITICAL-2: Async Session Management - HTTP Client in Naver Adapter
**Status:** [ ] Not Started [ ] In Progress [ ] Fixed [ ] Tested

**File:** `backend/app/scrapers/adapters/naver.py`

**Issues to Fix:**
- [ ] Line 103-104: HTTP client lifecycle management
- [ ] Add proper cleanup in `__init__` and error handlers
- [ ] Ensure cleanup() is called in all error paths

**Required Changes:**

Option A (Recommended - Context Manager per request):
```python
# In _call_api method
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.get(...)
    # Auto-closed after request
```

Option B (Persistent with guarantees):
```python
async def __init__(self):
    super().__init__()
    self.client_id = settings.NAVER_CLIENT_ID
    self.client_secret = settings.NAVER_CLIENT_SECRET
    self.http_client = httpx.AsyncClient(timeout=30.0)

async def __aenter__(self):
    return self

async def __aexit__(self, *args):
    await self.cleanup()
```

**Verification:**
```bash
# Run scraper for 1 hour and monitor connection count
# Should stay constant, not grow unbounded
lsof -p $(pgrep -f 'python.*naver') | grep TCP | wc -l
```

**Impact:** CAUSES memory leaks and eventual crashes

---

### CRITICAL-3: Deal Service - Incorrect Relationship Join
**Status:** [ ] Not Started [ ] In Progress [ ] Fixed [ ] Tested

**File:** `backend/app/services/deal_service.py`

**Issues to Fix:**
- [ ] Line 90-91: Fix category join in `get_deals()`
- [ ] Line 164: Fix category join in `get_top_deals()`
- [ ] Line 89-91: Change implicit join to explicit join

**Required Changes:**

**Before:**
```python
if category_slug:
    query = query.join(Category).where(Category.slug == category_slug)
```

**After:**
```python
if category_slug:
    query = query.join(Deal.category).where(Category.slug == category_slug)
```

**Verification:**
```bash
# Test category filtering:
curl "http://localhost:8000/api/v1/deals?category=electronics"
# Should return deals in that category without errors
```

**Impact:** BREAKS category filtering on deals

---

## HIGH ISSUES (8)

### HIGH-1: Frontend Type Mismatch - PriceHistoryPoint
**Status:** [ ] Not Started [ ] In Progress [ ] Fixed [ ] Tested

**Files:**
- [ ] `backend/app/schemas/product.py` - Add id and product_id fields
- [ ] `frontend/lib/types.ts` - Verify matches backend

**Required Changes:**

In `backend/app/schemas/product.py`:
```python
from uuid import UUID

class PriceHistoryPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    price: Decimal
    recorded_at: datetime
```

**Verification:**
```bash
# Test price history endpoint:
curl "http://localhost:8000/api/v1/products/{id}/price-history"
# Response should include id and product_id fields
```

**Impact:** Frontend cannot access price history data

---

### HIGH-2: Category Slug Inconsistency
**Status:** [ ] Not Started [ ] In Progress [ ] Fixed [ ] Tested

**Files to Audit:**
- [ ] `backend/app/db/seed.py` - Lines 203-209
- [ ] `frontend/lib/constants.ts` - Lines 46-55
- [ ] Backend database (after seed execution)

**Slugs to Standardize:**

| Category | Frontend Slug | Backend Slug | Correct Slug |
|----------|---------------|--------------|--------------|
| PC/Hardware | pc-hardware | pc-hardware | pc-hardware ✓ |
| Gaming | game-software | gaming | **CHOOSE ONE** |
| Smartphone | mobile-laptop | smartphones | **CHOOSE ONE** |

**Required Changes:**

1. Decide canonical slugs (recommend using backend slugs across both)
2. Update `frontend/lib/constants.ts` to match backend
3. Or update `backend/app/db/seed.py` to match frontend (not recommended)

**Verification:**
```bash
# Seed database
python -m app.db.seed

# Query categories
sqlite3 dealhawk.db "SELECT slug, name FROM categories ORDER BY slug"

# Verify each slug from frontend exists in backend
```

**Impact:** BREAKS category filtering and navigation

---

### HIGH-3: Deal Response Schema - Untyped price_history
**Status:** [ ] Not Started [ ] In Progress [ ] Fixed [ ] Tested

**File:** `backend/app/schemas/deal.py`

**Issue:**
- [ ] Line 62: `price_history: list = []` is untyped

**Required Changes:**

```python
from typing import List
from app.schemas.product import PriceHistoryPoint

class DealDetailResponse(DealResponse):
    description: Optional[str] = None
    starts_at: Optional[datetime] = None
    vote_down: int
    price_history: List[PriceHistoryPoint] = []
```

**Verification:**
```bash
# Test deal detail endpoint:
curl "http://localhost:8000/api/v1/deals/{id}"
# Should include properly typed price_history in OpenAPI docs
```

**Impact:** OpenAPI schema is incomplete, frontend type checking fails

---

### HIGH-4: Frontend API Client Configuration
**Status:** [ ] Not Started [ ] In Progress [ ] Fixed [ ] Tested

**Files:**
- [ ] `frontend/lib/api.ts` - API base URL
- [ ] `frontend/next.config.js` - API rewrites

**Issue:**
Environment variable mismatch between `NEXT_PUBLIC_API_URL` and `BACKEND_URL`

**Required Changes:**

**Option 1 (Recommended - Use rewrites):**

`frontend/lib/api.ts`:
```typescript
const API_BASE_URL = "";  // Empty = relative paths

export const apiClient = axios.create({
  baseURL: `/api/v1`,  // Relative path uses rewrites
  timeout: 10000,
  headers: {
    "Content-Type": "application/json",
  },
});
```

**Option 2 (Explicit configuration):**

`frontend/lib/api.ts`:
```typescript
const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
```

`frontend/next.config.js`:
```javascript
destination: `${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"}/api/:path*`,
```

**Verification:**
```bash
# Test in production build
NEXT_PUBLIC_BACKEND_URL=https://api.example.com npm run build

# Check that API requests go to correct URL
# Monitor Network tab in browser DevTools
```

**Impact:** API calls fail with CORS errors in production

---

### HIGH-5: Naver Adapter Error Handling
**Status:** [ ] Not Started [ ] In Progress [ ] Fixed [ ] Tested

**File:** `backend/app/scrapers/adapters/naver.py` Lines 142-185

**Issue:** Silent failure when all keywords fail to search

**Required Changes:**

```python
async def fetch_deals(self, category: Optional[str] = None) -> List[NormalizedDeal]:
    deals: List[NormalizedDeal] = []
    seen_product_ids = set()
    failed_categories = set()  # ADD THIS

    # ... existing code ...

    for cat_slug, keywords in keyword_groups.items():
        cat_failed = True  # ADD THIS
        for keyword in keywords:
            try:
                # ... fetch code ...
                cat_failed = False
                # Optionally break on success
            except Exception as e:
                logger.error(...)

        if cat_failed:  # ADD THIS CHECK
            failed_categories.add(cat_slug)

    # ADD WARNING IF NEEDED
    if failed_categories and not deals:
        logger.warning(
            "naver_fetch_complete_failure",
            message="All categories failed to fetch",
            failed_categories=list(failed_categories),
        )

    return deals
```

**Verification:**
```bash
# Test with invalid credentials
NAVER_CLIENT_ID=invalid NAVER_CLIENT_SECRET=invalid python -m app.scrapers.adapters.naver

# Should log warning about failure, not silently return empty list
```

**Impact:** Silent failures make production debugging difficult

---

### HIGH-6: Shop Filter Input Validation
**Status:** [ ] Not Started [ ] In Progress [ ] Fixed [ ] Tested

**Files:**
- [ ] `frontend/components/navigation/ShopFilter.tsx` - Frontend validation
- [ ] `backend/app/api/v1/deals.py` - Backend validation

**Required Changes:**

Frontend (`frontend/components/navigation/ShopFilter.tsx`):
```typescript
import { SHOPS } from "@/lib/constants";

const selectedShops = (searchParams.get("shop")?.split(",") || [])
  .filter(slug => SHOPS.some(shop => shop.slug === slug));
```

Backend (`backend/app/api/v1/deals.py`):
```python
@router.get("", response_model=ApiResponse)
async def list_deals(
    shop: Optional[str] = Query(None),
    ...
):
    """..."""
    if shop:
        # Validate shop exists
        shop_result = await db.execute(
            select(Shop).where(Shop.slug == shop)
        )
        if not shop_result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail=f"Unknown shop: {shop}"
            )

    service = DealService(db)
    deals, total = await service.get_deals(shop_slug=shop, ...)
```

**Verification:**
```bash
# Test invalid shop
curl "http://localhost:8000/api/v1/deals?shop=invalid"
# Should return 400 Bad Request

# Test valid shop
curl "http://localhost:8000/api/v1/deals?shop=naver"
# Should return deals from Naver
```

**Impact:** Invalid inputs cause unexpected behavior

---

### HIGH-7: Product Upsert Race Condition
**Status:** [ ] Not Started [ ] In Progress [ ] Fixed [ ] Tested

**File:** `backend/app/services/product_service.py` Lines 127-146

**Issue:** Concurrent upserts can create duplicate price history

**Required Changes:**

Add locking to prevent race condition:
```python
async def upsert_product(self, ...):
    # ... existing code ...

    # Flush to get ID
    await self.db.flush()

    # Acquire lock on product
    await self.db.execute(
        select(Product)
        .with_for_update()
        .where(Product.id == product.id)
    )

    # Re-check price recording after lock
    should_record = await self._should_record_price(
        product.id,
        normalized.current_price,
    )

    if should_record:
        price_record = PriceHistory(...)
        self.db.add(price_record)

    await self.db.commit()
```

**Verification:**
```bash
# Load test with concurrent requests
ab -n 1000 -c 50 "http://localhost:8000/api/v1/products/upsert"

# Check for duplicate price history entries
# Should have exactly 1 per unique product per second, not multiples
```

**Impact:** Data integrity issues in high-concurrency scenarios

---

### HIGH-8: Missing Deal Schema Required Fields
**Status:** [ ] Not Started [ ] In Progress [ ] Fixed [ ] Tested

**File:** `backend/app/schemas/deal.py` Line 61

**Issue:** `vote_down` has default value but should always be present

**Required Changes:**

```python
class DealDetailResponse(DealResponse):
    description: Optional[str] = None
    starts_at: Optional[datetime] = None
    vote_down: int  # Remove default = 0
    price_history: List[PriceHistoryPoint] = []
```

**Verification:**
```bash
# Test deal detail endpoint
curl "http://localhost:8000/api/v1/deals/{id}"

# Verify vote_down is always present and is a number
# not missing or undefined
```

**Impact:** Misleading API schema

---

## Testing Checklist

After fixing all critical and high issues, run:

### Unit Tests
```bash
cd backend
pytest tests/test_services.py -v
pytest tests/test_schemas.py -v (if exists)
```

### Integration Tests
```bash
# Test all category filters
curl "http://localhost:8000/api/v1/deals?category=pc-hardware"
curl "http://localhost:8000/api/v1/deals?category=gaming"
curl "http://localhost:8000/api/v1/deals?category=appliance-tv"

# Test all shop filters
curl "http://localhost:8000/api/v1/deals?shop=naver"
curl "http://localhost:8000/api/v1/deals?shop=coupang"

# Test pagination
curl "http://localhost:8000/api/v1/deals?page=2&limit=20"

# Test invalid inputs
curl "http://localhost:8000/api/v1/deals?category=invalid"
curl "http://localhost:8000/api/v1/deals?shop=invalid"
```

### Frontend Tests
```bash
cd frontend
npm run type-check
npm run build
npm run test
```

---

## Validation Checklist

- [ ] All 3 CRITICAL issues resolved
- [ ] All 8 HIGH issues resolved
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Frontend builds without TypeScript errors
- [ ] No console warnings in browser DevTools
- [ ] API docs in Swagger/OpenAPI are accurate
- [ ] Database seed executes successfully
- [ ] All category slugs are consistent between frontend and backend
- [ ] Environment variables are properly documented

---

## Sign-Off

| Role | Name | Date | Status |
|------|------|------|--------|
| QA Engineer | | | [ ] Approved |
| Backend Dev | | | [ ] Approved |
| Frontend Dev | | | [ ] Approved |
| Tech Lead | | | [ ] Approved |

---

## Notes

After all fixes are complete and tested:

1. Update version number in `backend/pyproject.toml` and `frontend/package.json`
2. Create git tag: `git tag -a v0.1.1 -m "Critical fixes for Phase 1"`
3. Document all changes in `CHANGELOG.md`
4. Schedule code review session
5. Plan Phase 2 work

