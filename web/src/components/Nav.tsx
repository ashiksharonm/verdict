import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import MobileNav from "./MobileNav";
import ThemeToggle from "./ThemeToggle";
import { REPO_URL } from "@/lib/config";

export const NAV_LINKS = [
  ["/playground", "Playground"],
  ["/docs", "Docs"],
  ["/benchmarks", "Benchmarks"],
  ["/dashboard", "Dashboard"],
] as const;

export default function Nav() {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-bg/90 backdrop-blur">
      <nav aria-label="Main" className="mx-auto grid max-w-6xl grid-cols-[1fr_auto] items-center gap-x-4 px-4 py-3 sm:px-6 md:grid-cols-[1fr_auto_1fr]">
        <Link href="/" className="text-xl font-medium tracking-tight">
          Verdict<span className="text-accent">.</span>
        </Link>
        <ul className="hidden items-center gap-x-7 md:flex">
          {NAV_LINKS.map(([href, label]) => (
            <li key={href}>
              <Link href={href} className="whitespace-nowrap text-sm text-muted transition-colors hover:text-ink">
                {label}
              </Link>
            </li>
          ))}
          <li>
            <a href={REPO_URL} className="inline-flex items-center gap-0.5 whitespace-nowrap text-sm text-muted transition-colors hover:text-ink">
              GitHub <ArrowUpRight aria-hidden className="size-3.5" />
            </a>
          </li>
        </ul>
        <div className="flex items-center justify-end gap-2">
          <ThemeToggle />
          <Link href="/login" className="btn btn-primary hidden sm:inline-flex">
            Sign in
          </Link>
          <MobileNav />
        </div>
      </nav>
    </header>
  );
}
