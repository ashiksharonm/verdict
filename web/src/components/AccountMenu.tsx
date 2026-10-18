"use client";
import { ChevronDown, FileText, KeyRound, LayoutDashboard, LogOut, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { useAuth } from "@/lib/useAuth";

const ITEMS = [
  ["/dashboard", "Dashboard", LayoutDashboard],
  ["/dashboard#keys", "API keys", KeyRound],
  ["/docs", "Docs", FileText],
] as const;

export function Avatar({ url, className = "size-5" }: { url: string | null; className?: string }) {
  // eslint-disable-next-line @next/next/no-img-element
  return url ? <img src={url} alt="" referrerPolicy="no-referrer" className={`${className} rounded-full`} /> : <UserRound aria-hidden className={className} />;
}

/** Desktop header slot: neutral placeholder, then "Sign in" or an account menu. */
export default function AccountMenu() {
  const { auth, signOut } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const btn = useRef<HTMLButtonElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    wrap.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
    const away = (e: PointerEvent) => {
      if (!wrap.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", away);
    return () => document.removeEventListener("pointerdown", away);
  }, [open]);

  if (auth.status === "loading") return <div aria-hidden className="skeleton hidden h-[42px] w-24 !rounded-full sm:block" />;
  if (auth.status === "anon")
    return (
      <Link href="/login" className="btn btn-primary hidden sm:inline-flex">
        Sign in
      </Link>
    );

  const close = (refocus: boolean) => {
    setOpen(false);
    if (refocus) btn.current?.focus();
  };
  const move = (dir: 1 | -1) => {
    const els = Array.from(wrap.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []);
    const i = els.indexOf(document.activeElement as HTMLElement);
    els[(i + dir + els.length) % els.length]?.focus();
  };

  return (
    <div
      ref={wrap}
      className="relative hidden sm:block"
      onKeyDown={(e) => {
        if (e.key === "Escape" && open) {
          e.stopPropagation();
          close(true);
        } else if (open && e.key === "ArrowDown") {
          e.preventDefault();
          move(1);
        } else if (open && e.key === "ArrowUp") {
          e.preventDefault();
          move(-1);
        } else if (open && e.key === "Tab") setOpen(false);
      }}
    >
      <button
        ref={btn}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        aria-label={`Account menu${auth.email ? `, ${auth.email}` : ""}`}
        className="btn btn-ghost !h-[42px] !gap-2 !px-3"
        onClick={() => setOpen((o) => !o)}
      >
        <Avatar url={auth.avatarUrl} />
        <span className="hidden max-w-[11rem] truncate text-sm lg:inline">{auth.email || "Account"}</span>
        <ChevronDown aria-hidden className="size-3.5 text-muted" />
      </button>
      {open && (
        <div id={id} role="menu" aria-label="Account" className="card absolute right-0 top-full z-40 mt-2 w-56 p-1.5">
          {auth.email && <p className="truncate px-3 py-2 text-xs text-muted">{auth.email}</p>}
          {ITEMS.map(([href, label, Icon]) => (
            <Link key={href} href={href} role="menuitem" tabIndex={-1} onClick={() => close(false)} className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-tint focus-visible:bg-tint">
              <Icon aria-hidden className="size-4 text-muted" />
              {label}
            </Link>
          ))}
          <button
            type="button"
            role="menuitem"
            tabIndex={-1}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-tint focus-visible:bg-tint"
            onClick={async () => {
              close(false);
              await signOut();
              router.push("/");
              router.refresh();
            }}
          >
            <LogOut aria-hidden className="size-4 text-muted" />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
