import type { Metadata } from "next";
import Playground from "@/components/Playground";

export const metadata: Metadata = { title: "Playground" };

export default function Page() {
  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold">Playground</h1>
      <p className="max-w-2xl text-muted">
        Try the checks live. The free-tier API sleeps when idle, so the first request can take up to a minute. Text is not stored by default and is limited per IP.
      </p>
      <Playground />
    </div>
  );
}
