import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-8">
      <h2 className="mb-4 text-4xl font-bold text-accent">404</h2>
      <p className="mb-6 text-lg text-gray-400">페이지를 찾을 수 없습니다</p>
      <Link href="/" className="btn-primary">
        홈으로 돌아가기
      </Link>
    </div>
  );
}
