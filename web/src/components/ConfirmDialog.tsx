"use client";
import { useEffect, useRef } from "react";

/** Native modal dialog: traps focus, closes on Escape, and returns focus to the opener. */
export default function ConfirmDialog({ open, title, body, confirmLabel, onConfirm, onCancel }: { open: boolean; title: string; body: string; confirmLabel: string; onConfirm: () => void; onCancel: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} aria-labelledby="confirm-title" onClose={onCancel} onCancel={onCancel}>
      <div className="w-[26rem] max-w-full space-y-4 p-6">
        <h2 id="confirm-title" className="text-xl font-medium">{title}</h2>
        <p className="text-sm text-muted">{body}</p>
        <div className="flex justify-end gap-2">
          <button type="button" className="btn btn-ghost" autoFocus onClick={onCancel}>Cancel</button>
          <button type="button" className="btn btn-primary !bg-bad !text-accent-fg" onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </dialog>
  );
}
