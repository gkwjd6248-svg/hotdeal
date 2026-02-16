import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-8">
      <h2 className="mb-4 text-4xl font-bold text-accent">404</h2>
      <p className="mb-6 text-lg text-gray-400">Page not found</p>
      <Link href="/" className="btn-primary">
        Go back home
      </Link>
    </div>
  );
}
