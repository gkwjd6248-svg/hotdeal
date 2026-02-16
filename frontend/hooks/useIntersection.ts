"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Intersection Observer hook for infinite scroll triggers.
 * Returns a ref to attach to a sentinel element and a boolean
 * indicating whether that element is currently in the viewport.
 */
export function useIntersection(options?: IntersectionObserverInit) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [isIntersecting, setIsIntersecting] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(([entry]) => {
      setIsIntersecting(entry.isIntersecting);
    }, options);

    observer.observe(el);
    return () => observer.disconnect();
  }, [options]);

  return { ref, isIntersecting };
}
