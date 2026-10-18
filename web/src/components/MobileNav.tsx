"use client";
import { ArrowUpRight, KeyRound, LogOut, Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { REPO_URL } from "@/lib/config";
import { useAuth } from "@/lib/useAuth";
import { Avatar } from "./AccountMenu";

const LINKS = [
  ["/playground", "Playground"],
  ["/docs", "Docs"],
  ["/benchmarks", "Benchmarks"],
  ["/dashboard", "Dashboard"],
] as const;

/** Slide-in sheet built on the native modal dialog, which traps focus, closes on Escape and restores focus to the button. */
export default function MobileNav() {
  const ref = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(false);
  const path = usePathname();
  const router = useRouter();
  const { auth, signOut } = useAuth();
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
            {auth.status === "anon" && (
              <li>
                <Link href="/login" className="block rounded-xl px-3 py-3 text-lg font-light hover:bg-tint">Sign in</Link>
              </li>
            )}
            <li>
              <a href={REPO_URL} className="flex items-center gap-1 rounded-xl px-3 py-3 text-lg font-light hover:bg-tint">
                GitHub <ArrowUpRight aria-hidden className="size-4" />
              </a>
            </li>
          </ul>
          {auth.status === "user" && (
            <div className="mt-4 border-t border-border pt-4">
              <p className="flex items-center gap-2 px-3 pb-2 text-sm text-muted">
                <Avatar url={auth.avatarUrl} />
                <span className="truncate">{auth.email || "Signed in"}</span>
              </p>
              <ul className="space-y-1">
                <li>
                  <Link href="/dashboard#keys" onClick={() => setOpen(false)} className="flex items-center gap-2 rounded-xl px-3 py-3 text-lg font-light hover:bg-tint"><KeyRound aria-hidden className="size-4" />API keys</Link>
                </li>
                <li>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-3 text-left text-lg font-light hover:bg-tint"
                    onClick={async () => {
                      setOpen(false);
                      await signOut();
                      router.push("/");
                      router.refresh();
                    }}
                  >
                    <LogOut aria-hidden className="size-4" />Sign out
                  </button>
                </li>
              </ul>
            </div>
          )}
          {auth.status === "loading" && <div aria-hidden className="skeleton mx-3 mt-4 h-6 w-32" />}
        </div>
      </dialog>
    </div>
  );
}
