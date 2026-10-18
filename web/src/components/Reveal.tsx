"use client";
import { useEffect, useRef } from "react";

/** Fades a block in once when it first scrolls into view. Content is visible without JS and under reduced motion (see globals.css). */
export default function Reveal({ children, className = "", as: Tag = "div", ...rest }: { children: React.ReactNode; className?: string; as?: "div" | "section"; [k: string]: unknown }) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") return el.classList.add("in");
    const io = new IntersectionObserver(
      (es) => es.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add("in");
          io.unobserve(e.target);
        }
      }),
      { rootMargin: "0px 0px -8% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <Tag ref={ref as never} className={`reveal ${className}`} {...rest}>
      {children}
    </Tag>
  );
}
