"use client";

import { useEffect, useRef, useState } from "react";

interface UseIntersectionOptions {
  threshold?: number;
  rootMargin?: string;
}

/**
 * Intersection Observer hook for infinite scroll triggers.
 * Returns a ref to attach to a sentinel element and a boolean
 * indicating whether that element is currently in the viewport.
 * Options are intentionally stable — pass literal values, not computed objects.
 */
export function useIntersection(options?: UseIntersectionOptions) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [isIntersecting, setIsIntersecting] = useState(false);
  const threshold = options?.threshold;
  const rootMargin = options?.rootMargin;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsIntersecting(entry.isIntersecting);
      },
      { threshold, rootMargin }
    );

    observer.observe(el);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threshold, rootMargin]);

  return { ref, isIntersecting };
}
