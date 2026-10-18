"use client";
import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { useToast } from "./Toast";

export default function CopyButton({ text, label, children, className = "btn btn-ghost !py-1.5" }: { text: string | (() => string); label: string; children?: React.ReactNode; className?: string }) {
  const [done, setDone] = useState(false);
  const toast = useToast();
  return (
    <button
      type="button"
      aria-label={children ? undefined : label}
      className={className}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(typeof text === "function" ? text() : text);
          setDone(true);
          toast(`${label}: copied`);
          setTimeout(() => setDone(false), 1800);
        } catch {
          toast("Could not copy to the clipboard", "error");
        }
      }}
    >
      {done ? <Check aria-hidden className="size-4 text-ok" /> : <Copy aria-hidden className="size-4" />}
      {children && <span>{done ? "Copied" : children}</span>}
    </button>
  );
}
