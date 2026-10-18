import type { Metadata } from "next";
import Playground from "@/components/Playground";

export const metadata: Metadata = { title: "Playground" };

export default function Page() {
  return (
    <div>
      <p className="eyebrow">Playground</p>
      <h1 className="display mt-3">Try the checks live</h1>
      <p className="lede mb-10 mt-5 max-w-2xl">
        The free-tier API sleeps when idle, so the first request can take up to a minute. Text is not stored by default and is limited per IP.
      </p>
      <Playground />
    </div>
  );
}
