"use client";
import { ArrowUpRight, Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { REPO_URL } from "@/lib/config";

const LINKS = [
  ["/playground", "Playground"],
  ["/docs", "Docs"],
  ["/benchmarks", "Benchmarks"],
  ["/dashboard", "Dashboard"],
  ["/login", "Sign in"],
] as const;

/** Slide-in sheet built on the native modal dialog, which traps focus, closes on Escape and restores focus to the button. */
export default function MobileNav() {
  const ref = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(false);
  const path = usePathname();
  useEffect(() => {
    ref.current?.close();
  }, [path]);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <div className="md:hidden">
      <button type="button" aria-label="Open menu" aria-haspopup="dialog" className="btn btn-ghost !p-2.5" onClick={() => setOpen(true)}>
        <Menu aria-hidden className="size-4" />
      </button>
      <dialog
        ref={ref}
        className="sheet"
        aria-label="Menu"
        onClose={() => setOpen(false)}
        onClick={(e) => {
          if (e.target === ref.current) setOpen(false);
        }}
      >
        <div className="flex h-full flex-col p-5">
          <button type="button" aria-label="Close menu" className="btn btn-ghost mb-4 self-end !p-2.5" onClick={() => setOpen(false)}>
            <X aria-hidden className="size-4" />
          </button>
          <ul className="space-y-1">
            {LINKS.map(([href, label]) => (
              <li key={href}>
                <Link href={href} className="block rounded-xl px-3 py-3 text-lg font-light hover:bg-tint" aria-current={path === href ? "page" : undefined}>
                  {label}
                </Link>
              </li>
            ))}
            <li>
              <a href={REPO_URL} className="flex items-center gap-1 rounded-xl px-3 py-3 text-lg font-light hover:bg-tint">
                GitHub <ArrowUpRight aria-hidden className="size-4" />
              </a>
            </li>
          </ul>
        </div>
      </dialog>
    </div>
  );
}
