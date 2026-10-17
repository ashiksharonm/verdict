"use client";
import { useState } from "react";

type Theme = "light" | "dark";
const current = (): Theme => {
  if (typeof document === "undefined") return "light";
  const t = document.documentElement.dataset.theme;
  if (t === "dark" || t === "light") return t;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
};

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | null>(null);
  const shown = theme ?? "light";
  return (
    <button
      type="button"
      aria-label={`Switch to ${shown === "dark" ? "light" : "dark"} theme`}
      className="rounded-md border border-border px-2.5 py-1 text-sm hover:bg-code"
      onClick={() => {
        const next: Theme = (theme ?? current()) === "dark" ? "light" : "dark";
        document.documentElement.dataset.theme = next;
        try {
          localStorage.setItem("theme", next);
        } catch {}
        setTheme(next);
      }}
      suppressHydrationWarning
    >
      {theme === null ? "Theme" : theme === "dark" ? "Light" : "Dark"}
    </button>
  );
}
