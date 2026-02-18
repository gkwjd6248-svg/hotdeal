/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      // Development / placeholder images
      { protocol: "https", hostname: "images.unsplash.com" },
      // Korean Shopping Malls
      { protocol: "https", hostname: "shopping-phinf.pstatic.net" },
      { protocol: "https", hostname: "*.naver.com" },
      { protocol: "https", hostname: "*.naver.net" },
      { protocol: "https", hostname: "thumbnail*.coupangcdn.com" },
      { protocol: "https", hostname: "*.coupangcdn.com" },
      { protocol: "https", hostname: "*.coupang.com" },
      { protocol: "https", hostname: "*.11st.co.kr" },
      { protocol: "https", hostname: "*.gmarket.co.kr" },
      { protocol: "https", hostname: "*.auction.co.kr" },
      { protocol: "https", hostname: "*.tmon.co.kr" },
      { protocol: "https", hostname: "*.wemakeprice.com" },
      { protocol: "https", hostname: "*.ssg.com" },
      { protocol: "https", hostname: "*.lotteon.com" },
      { protocol: "https", hostname: "*.kurly.com" },
      { protocol: "https", hostname: "*.musinsa.com" },
      { protocol: "https", hostname: "*.musinsa.net" },
      { protocol: "https", hostname: "*.oliveyoung.co.kr" },
      { protocol: "https", hostname: "*.e-himart.co.kr" },
      { protocol: "https", hostname: "*.himart.co.kr" },
      { protocol: "https", hostname: "*.ssfshop.com" },
      { protocol: "https", hostname: "*.interpark.com" },
      // Global Shopping Malls
      { protocol: "https", hostname: "*.aliexpress.com" },
      { protocol: "https", hostname: "ae01.alicdn.com" },
      { protocol: "https", hostname: "*.alicdn.com" },
      { protocol: "https", hostname: "*.amazon.com" },
      { protocol: "https", hostname: "m.media-amazon.com" },
      { protocol: "https", hostname: "*.ebay.com" },
      { protocol: "https", hostname: "i.ebayimg.com" },
      { protocol: "https", hostname: "*.iherb.com" },
      { protocol: "https", hostname: "*.newegg.com" },
      { protocol: "https", hostname: "c1.neweggimages.com" },
      // Steam / Gaming
      { protocol: "https", hostname: "shared.akamai.steamstatic.com" },
      { protocol: "https", hostname: "*.steamstatic.com" },
      { protocol: "https", hostname: "cdn.akamai.steamstatic.com" },
      { protocol: "https", hostname: "store.akamai.steamstatic.com" },
      // General CDNs (for shops adding new image sources)
      { protocol: "https", hostname: "*.cloudfront.net" },
      { protocol: "https", hostname: "*.googleapis.com" },
      { protocol: "https", hostname: "*.ggpht.com" },
    ],
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL || "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
