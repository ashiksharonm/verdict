"use client";
import { ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";

export type TocItem = { id: string; label: string; sub?: boolean };

/** Sticky table of contents; the item whose heading is nearest the top of the viewport is marked current. */
export default function Toc({ items, title = "On this page" }: { items: TocItem[]; title?: string }) {
  const [active, setActive] = useState(items[0]?.id ?? "");
  useEffect(() => {
    const els = items.map((i) => document.getElementById(i.id)).filter((e): e is HTMLElement => Boolean(e));
    const io = new IntersectionObserver(
      (entries) => {
        const hit = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        if (hit) setActive(hit.target.id);
      },
      { rootMargin: "-90px 0px -65% 0px" },
    );
    els.forEach((e) => io.observe(e));
    return () => io.disconnect();
  }, [items]);
  const list = items.map((i) => (
    <a key={i.id} href={`#${i.id}`} className={i.sub ? "sub" : ""} aria-current={active === i.id ? "true" : undefined}>
      <span className="flex items-center justify-between gap-2">
        <span>{i.label}</span>
        <ChevronRight aria-hidden className="mark size-3.5 shrink-0" />
      </span>
    </a>
  ));
  return (
    <>
      <nav aria-label={title} className="toc sticky top-24 hidden max-h-[calc(100vh-8rem)] overflow-y-auto lg:block">
        <p className="eyebrow mb-3 !text-muted">{title}</p>
        {list}
      </nav>
      <details className="card mb-6 px-4 py-3 lg:hidden">
        <summary className="eyebrow cursor-pointer !text-muted">{title}</summary>
        <nav aria-label={`${title} (compact)`} className="toc mt-3">{list}</nav>
      </details>
    </>
  );
}
