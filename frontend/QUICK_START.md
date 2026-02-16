# DealHawk Frontend - Quick Start Guide

## Prerequisites

- Node.js 18+ installed
- npm or yarn package manager
- All dependencies already installed (check package.json)

## Starting Development Server

```bash
# Navigate to frontend directory
cd C:\Users\gkwjd\Downloads\shopping\frontend

# Start development server
npm run dev

# Or with yarn
yarn dev
```

The application will be available at: **http://localhost:3000**

## Testing Pages

### 1. Homepage (/)
- **URL**: http://localhost:3000/
- **Features to test**:
  - Hero section with "AI가 찾은 오늘의 특가"
  - Trending keywords display (desktop only)
  - Category tabs navigation
  - Shop filter (multi-select)
  - Sort dropdown (최신순, AI추천순, 할인율순, 조회순)
  - 12 mock deal cards in responsive grid
  - Search bar in header
  - Footer links

### 2. All Deals Page (/deals)
- **URL**: http://localhost:3000/deals
- **Features to test**:
  - Same as homepage but without hero section
  - URL params filtering:
    - Category: `/deals?category=pc-hardware`
    - Shop: `/deals?shop=coupang,naver`
    - Sort: `/deals?sort=discount`
    - Combined: `/deals?category=mobile-laptop&shop=coupang&sort=score`

### 3. Deal Detail Page (/deals/[id])
- **URLs to test**:
  - http://localhost:3000/deals/1 (삼성 갤럭시 버즈2)
  - http://localhost:3000/deals/2 (LG 그램 노트북)
  - http://localhost:3000/deals/3 (다이슨 청소기)
  - http://localhost:3000/deals/12 (AMD 라이젠 CPU)
- **Features to test**:
  - Large product image
  - Price display with discount
  - AI score card with reasoning
  - Meta info (time, views, votes)
  - "특가 바로가기" button (opens external link)
  - Breadcrumb navigation
  - Expiry notice (deal #3 and #6 have expires_at)
  - Comments section placeholder

### 4. Search Page (/search)
- **URLs to test**:
  - http://localhost:3000/search?q=삼성
  - http://localhost:3000/search?q=노트북
  - http://localhost:3000/search?q=청소기
  - http://localhost:3000/search?q=애플
  - http://localhost:3000/search?q=nonexistent (should show empty state)
- **Features to test**:
  - Search query displayed in heading
  - Results count
  - Filtered deal cards
  - Empty state when no results
  - Shop filter works with search
  - Sort dropdown works with search

## Testing Interactions

### Category Navigation
1. Click any category tab in header
2. Verify URL changes to `/deals?category=...`
3. Verify deals are filtered by category
4. Click "전체" to see all deals

### Shop Filter
1. Click shop chips below category tabs
2. Verify multiple shops can be selected (multi-select)
3. Verify URL updates with comma-separated shops
4. Click "전체" to clear all filters
5. Verify checkmarks appear on selected shops

### Search
1. Click search bar in header
2. Verify trending keywords dropdown appears
3. Click a trending keyword
4. Verify navigation to `/search?q=...`
5. Type in search bar
6. Press Enter or click search button
7. Verify search results page

### Sort Dropdown
1. Click sort dropdown
2. Select different sort options
3. Verify deals reorder correctly:
   - **최신순**: Most recent first
   - **AI추천순**: Highest AI score first
   - **할인율순**: Highest discount % first
   - **조회순**: Most views first

### Deal Card Interactions
1. Hover over deal card
2. Verify hover effects:
   - Card scales up slightly
   - Border glows orange
   - Background lightens
3. Click deal card
4. Verify navigation to detail page

### Deal Detail Page
1. Click breadcrumb links
2. Verify navigation
3. Click category badge
4. Verify filtered deals page
5. Click "특가 바로가기" button
6. Verify external link opens (currently dummy URLs)

## Testing Responsive Design

### Mobile (< 640px)
```bash
# Open Chrome DevTools
# Set device to iPhone 12 (390px)
```
- Verify 1 column grid
- Verify horizontal scroll on category tabs
- Verify horizontal scroll on shop filter
- Verify search bar takes full width
- Verify hero section responsive
- Verify footer stacks vertically

### Tablet (640px - 1024px)
```bash
# Set device to iPad (768px)
```
- Verify 2 column grid
- Verify category tabs don't overflow
- Verify header layout

### Desktop (1024px+)
```bash
# Set device to Desktop (1440px)
```
- Verify 3-4 column grid
- Verify trending keywords show on homepage
- Verify all elements visible
- Verify max-width constraint (1440px)

## Checking TypeScript Types

```bash
# Run TypeScript compiler
npm run type-check

# Or with yarn
yarn type-check
```

Should complete with no errors.

## Building for Production

```bash
# Build optimized production bundle
npm run build

# Should complete successfully with:
# - No TypeScript errors
# - No build errors
# - Static page generation for routes
```

## Testing Mock Data

All pages use `MOCK_DEALS` from `lib/mock-data.ts`:
- 12 realistic Korean products
- Various categories and shops
- Different time ranges (2h to 24h ago)
- Realistic prices and discounts
- AI scores between 75-95
- View counts, votes, comments

To modify mock data:
1. Edit `C:\Users\gkwjd\Downloads\shopping\frontend\lib\mock-data.ts`
2. Restart dev server
3. Changes will appear immediately

## Common Issues & Solutions

### Issue: Port 3000 already in use
```bash
# Solution: Use a different port
npm run dev -- -p 3001
```

### Issue: Images not loading
- Mock data uses Unsplash URLs
- Requires internet connection
- If offline, images show placeholder emoji

### Issue: Trending keywords dropdown not closing
- Click outside the search bar area
- useEffect handles click-outside detection

### Issue: Category filter not working
- Verify searchParams are passed to page component
- Check URL has correct format: `?category=slug`
- Ensure category slug matches one in CATEGORIES array

### Issue: Shop filter selections not showing
- Verify shop slugs in URL match SHOPS array
- Format should be: `?shop=coupang,naver` (comma-separated)

## Next Steps After Testing

1. **Connect to Backend API**
   - Replace `MOCK_DEALS` with API calls
   - Use `apiClient` from `lib/api.ts`
   - Add error handling
   - Implement loading states

2. **Add Real Data**
   - Fetch deals from `/api/v1/deals`
   - Fetch categories from `/api/v1/categories`
   - Fetch shops from `/api/v1/shops`
   - Implement search API integration

3. **Implement Pagination**
   - Add infinite scroll
   - Or add "Load More" button
   - Track page number in URL params

4. **Add Advanced Features**
   - User authentication
   - Deal voting system
   - Comments functionality
   - Price history charts
   - Email alerts

## Testing Checklist

- [ ] Homepage loads with all components
- [ ] All 12 mock deals display correctly
- [ ] Category tabs navigate and filter
- [ ] Shop filter multi-select works
- [ ] Sort dropdown reorders deals
- [ ] Search bar shows trending keywords
- [ ] Search navigates to results page
- [ ] Deal cards have hover effects
- [ ] Clicking deal card goes to detail page
- [ ] Deal detail page shows all info
- [ ] Breadcrumb navigation works
- [ ] External link button works
- [ ] Footer links present
- [ ] Mobile responsive (1 column)
- [ ] Tablet responsive (2 columns)
- [ ] Desktop responsive (3-4 columns)
- [ ] No console errors
- [ ] TypeScript builds without errors
- [ ] Production build succeeds

---

**Status**: Ready for development testing
**Next**: Run `npm run dev` and test all features
**Support**: Check BUILD_SUMMARY.md for detailed documentation
