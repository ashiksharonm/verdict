"use client";
import { CircleAlert, CircleCheck } from "lucide-react";
import { createContext, useCallback, useContext, useState } from "react";

type Toast = { id: number; text: string; kind: "ok" | "error" };
const Ctx = createContext<(text: string, kind?: Toast["kind"]) => void>(() => {});
export const useToast = () => useContext(Ctx);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, kind: Toast["kind"] = "ok") => {
    const id = Date.now() + Math.random();
    setItems((p) => [...p.slice(-2), { id, text, kind }]);
    setTimeout(() => setItems((p) => p.filter((t) => t.id !== id)), kind === "error" ? 6000 : 3500);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div role="status" aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex flex-col items-center gap-2 px-4">
        {items.map((t) => (
          <div key={t.id} className="rise pointer-events-auto flex max-w-md items-start gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm shadow-[var(--shadow)]">
            {t.kind === "ok" ? <CircleCheck aria-hidden className="mt-0.5 size-4 shrink-0 text-ok" /> : <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-bad" />}
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
