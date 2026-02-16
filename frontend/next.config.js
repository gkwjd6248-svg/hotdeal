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
      { protocol: "https", hostname: "*.oliveyoung.co.kr" },
      // Global Shopping Malls
      { protocol: "https", hostname: "*.aliexpress.com" },
      { protocol: "https", hostname: "ae01.alicdn.com" },
      { protocol: "https", hostname: "*.amazon.com" },
      { protocol: "https", hostname: "m.media-amazon.com" },
      { protocol: "https", hostname: "*.ebay.com" },
      { protocol: "https", hostname: "i.ebayimg.com" },
      { protocol: "https", hostname: "*.iherb.com" },
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
