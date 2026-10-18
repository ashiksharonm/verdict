"use client";
import { ArrowUp } from "lucide-react";
import { useEffect, useState } from "react";
import { prefersReducedMotion } from "@/lib/motion";

export default function BackToTop() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    const on = () => setShow(window.scrollY > 900);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  return (
    <button
      type="button"
      aria-label="Back to top"
      tabIndex={show ? 0 : -1}
      onClick={() => window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? "auto" : "smooth" })}
      className={`btn btn-ghost fixed bottom-5 right-5 z-40 !p-3 shadow-[var(--shadow)] transition-opacity ${show ? "opacity-100" : "pointer-events-none opacity-0"}`}
    >
      <ArrowUp aria-hidden className="size-4" />
    </button>
  );
}
