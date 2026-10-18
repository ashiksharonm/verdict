"use client";
import { Moon, Sun } from "lucide-react";
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
      className="btn btn-ghost !p-2.5"
      onClick={() => {
        const next: Theme = (theme ?? current()) === "dark" ? "light" : "dark";
        const root = document.documentElement;
        root.classList.add("theme-anim");
        root.dataset.theme = next;
        setTimeout(() => root.classList.remove("theme-anim"), 350);
        try {
          localStorage.setItem("theme", next);
        } catch {}
        setTheme(next);
      }}
      suppressHydrationWarning
    >
      {/* Both icons render; CSS shows the one for the active theme so there is no flash or hydration mismatch. */}
      <Sun aria-hidden className="theme-sun size-4" />
      <Moon aria-hidden className="theme-moon size-4" />
    </button>
  );
}
