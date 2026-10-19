import type { Metadata } from "next";
import Playground from "@/components/Playground";
import { liveMs } from "@/lib/live";

export const metadata: Metadata = { title: "Playground" };

export default function Page() {
  return (
    <div>
      <p className="eyebrow">Playground</p>
      <h1 className="display mt-3">Try the checks live</h1>
      <p className="lede mb-10 mt-5 max-w-2xl">
        The API scales to zero when idle, so the first request pays a model load of about {liveMs.loadS} s plus container start; after that a 3-check request takes about {liveMs.p50} ms server-side. Text is not stored by default and is limited per IP.
      </p>
      <Playground />
    </div>
  );
}
