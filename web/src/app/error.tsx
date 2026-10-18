"use client";
import { RotateCw } from "lucide-react";
import Link from "next/link";

export default function Error({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div role="alert" className="mx-auto max-w-xl py-16 text-center">
      <p className="eyebrow">Something went wrong</p>
      <h1 className="display mt-3">This page hit an error</h1>
      <p className="lede mt-5">Your data is safe. Try again, and if it keeps happening, go back to the home page.</p>
      <div className="mt-8 flex justify-center gap-3">
        <button type="button" onClick={reset} className="btn btn-primary"><RotateCw aria-hidden className="size-4" />Try again</button>
        <Link href="/" className="btn btn-ghost">Back home</Link>
      </div>
    </div>
  );
}
