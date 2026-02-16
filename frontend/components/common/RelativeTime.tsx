"use client";

import { useState, useEffect } from "react";
import { formatDistanceToNow } from "date-fns";
import { ko } from "date-fns/locale";

interface RelativeTimeProps {
  date: string;
  suffix?: boolean;
}

export default function RelativeTime({
  date,
  suffix = true,
}: RelativeTimeProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Render placeholder on server to avoid hydration mismatch
  if (!mounted) {
    return <span className="text-xs text-gray-400">&nbsp;</span>;
  }

  try {
    const timeAgo = formatDistanceToNow(new Date(date), {
      addSuffix: suffix,
      locale: ko,
    });

    return <span className="text-xs text-gray-400">{timeAgo}</span>;
  } catch {
    return <span className="text-xs text-gray-400">-</span>;
  }
}
