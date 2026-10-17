import Link from "next/link";
import ThemeToggle from "./ThemeToggle";
import { REPO_URL } from "@/lib/config";

const links = [
  ["/playground", "Playground"],
  ["/docs", "Docs"],
  ["/benchmarks", "Benchmarks"],
  ["/dashboard", "Dashboard"],
] as const;

export default function Nav() {
  return (
    <header className="border-b border-border">
      <nav aria-label="Main" className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-5 gap-y-2 px-4 py-3">
        <Link href="/" className="mr-2 text-lg font-bold tracking-tight">
          Verdict
        </Link>
        {links.map(([href, label]) => (
          <Link key={href} href={href} className="text-sm text-muted hover:text-fg">
            {label}
          </Link>
        ))}
        <a href={REPO_URL} className="text-sm text-muted hover:text-fg">
          GitHub
        </a>
        <div className="ml-auto">
          <ThemeToggle />
        </div>
      </nav>
    </header>
  );
}
