# DealHawk Frontend - File Reference

Quick reference for all created/modified files with absolute paths.

## Core Application Files

### Layout & Global Styles
- `C:\Users\gkwjd\Downloads\shopping\frontend\app\layout.tsx`
- `C:\Users\gkwjd\Downloads\shopping\frontend\app\globals.css`

### Pages
- `C:\Users\gkwjd\Downloads\shopping\frontend\app\page.tsx` (Homepage)
- `C:\Users\gkwjd\Downloads\shopping\frontend\app\deals\page.tsx` (Deal listing)
- `C:\Users\gkwjd\Downloads\shopping\frontend\app\deals\[id]\page.tsx` (Deal detail)
- `C:\Users\gkwjd\Downloads\shopping\frontend\app\search\page.tsx` (Search results)

## Component Files

### Navigation Components
- `C:\Users\gkwjd\Downloads\shopping\frontend\components\navigation\Header.tsx`
- `C:\Users\gkwjd\Downloads\shopping\frontend\components\navigation\Footer.tsx`
- `C:\Users\gkwjd\Downloads\shopping\frontend\components\navigation\CategoryTabs.tsx`
- `C:\Users\gkwjd\Downloads\shopping\frontend\components\navigation\ShopFilter.tsx`
- `C:\Users\gkwjd\Downloads\shopping\frontend\components\navigation\SortDropdown.tsx`

### Common Components
- `C:\Users\gkwjd\Downloads\shopping\frontend\components\common\PriceDisplay.tsx`
- `C:\Users\gkwjd\Downloads\shopping\frontend\components\common\RelativeTime.tsx`
- `C:\Users\gkwjd\Downloads\shopping\frontend\components\common\ShopLogo.tsx`
- `C:\Users\gkwjd\Downloads\shopping\frontend\components\common\EmptyState.tsx`

### Deal Components
- `C:\Users\gkwjd\Downloads\shopping\frontend\components\deals\DealCard.tsx`
- `C:\Users\gkwjd\Downloads\shopping\frontend\components\deals\DealCardSkeleton.tsx`
- `C:\Users\gkwjd\Downloads\shopping\frontend\components\deals\DealGrid.tsx`

### Search Components
- `C:\Users\gkwjd\Downloads\shopping\frontend\components\search\SearchBar.tsx`
- `C:\Users\gkwjd\Downloads\shopping\frontend\components\search\TrendingKeywords.tsx`

## Library Files

### Type Definitions & Constants
- `C:\Users\gkwjd\Downloads\shopping\frontend\lib\types.ts`
- `C:\Users\gkwjd\Downloads\shopping\frontend\lib\constants.ts`
- `C:\Users\gkwjd\Downloads\shopping\frontend\lib\utils.ts`
- `C:\Users\gkwjd\Downloads\shopping\frontend\lib\api.ts`
- `C:\Users\gkwjd\Downloads\shopping\frontend\lib\mock-data.ts`

## Configuration Files
- `C:\Users\gkwjd\Downloads\shopping\frontend\tailwind.config.ts`
- `C:\Users\gkwjd\Downloads\shopping\frontend\package.json`
- `C:\Users\gkwjd\Downloads\shopping\frontend\next.config.js`
- `C:\Users\gkwjd\Downloads\shopping\frontend\tsconfig.json`

## Documentation
- `C:\Users\gkwjd\Downloads\shopping\frontend\BUILD_SUMMARY.md`
- `C:\Users\gkwjd\Downloads\shopping\frontend\FILE_REFERENCE.md` (this file)

---

## Quick Import Paths

Using Next.js `@/` alias (configured in tsconfig.json):

```typescript
// Components
import Header from "@/components/navigation/Header";
import DealCard from "@/components/deals/DealCard";
import PriceDisplay from "@/components/common/PriceDisplay";
import SearchBar from "@/components/search/SearchBar";

// Library
import { Deal } from "@/lib/types";
import { CATEGORIES, SHOPS } from "@/lib/constants";
import { formatPrice, cn } from "@/lib/utils";
import { MOCK_DEALS } from "@/lib/mock-data";
import { apiClient } from "@/lib/api";
```

## Icon Usage

From `lucide-react`:
- Flame (logo)
- Search (search bar)
- Sparkles (AI badge)
- Eye, ThumbsUp, MessageCircle (stats)
- Clock (time)
- ExternalLink (CTA)
- Store (shop)
- PackageOpen (empty state)
- Github (footer)
- Category icons: Laptop, CreditCard, Gamepad2, Smartphone, Tv, ShoppingBag, Plane

All categories in constants.ts have their icon defined.
