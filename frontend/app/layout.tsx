import type { Metadata } from "next";
import "./globals.css";
import Header from "@/components/navigation/Header";
import Footer from "@/components/navigation/Footer";
import Providers from "@/components/Providers";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_BASE_URL || "http://localhost:3000"),
  title: {
    default: "DealHawk - AI 특가 집합",
    template: "%s | DealHawk",
  },
  description:
    "AI가 18개 쇼핑몰에서 자동으로 찾은 최저가 특가 정보",
  keywords: [
    "특가",
    "할인",
    "쇼핑",
    "가격비교",
    "쿠팡",
    "네이버쇼핑",
    "11번가",
    "알리익스프레스",
    "아마존",
    "AI 추천",
    "최저가",
  ],
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  openGraph: {
    type: "website",
    locale: "ko_KR",
    url: "/",
    siteName: "DealHawk",
    title: "DealHawk - AI 특가 집합",
    description: "AI가 18개 쇼핑몰에서 자동으로 찾은 최저가 특가 정보",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "DealHawk - AI 특가 집합",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "DealHawk - AI 특가 집합",
    description: "AI가 18개 쇼핑몰에서 자동으로 찾은 최저가 특가 정보",
    images: ["/og-image.png"],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko" className="dark">
      <head>
        <link
          rel="stylesheet"
          as="style"
          crossOrigin="anonymous"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css"
        />
      </head>
      <body className="flex min-h-screen flex-col bg-background text-gray-200 antialiased">
        <Providers>
          <Header />
          <main className="flex-1">{children}</main>
          <Footer />
        </Providers>
      </body>
    </html>
  );
}
