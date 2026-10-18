import Link from "next/link";
import BackToTop from "./BackToTop";
import Toc, { type TocItem } from "./Toc";

export default function DocLayout({ eyebrow, title, intro, toc, children }: { eyebrow: string; title: string; intro: React.ReactNode; toc: TocItem[]; children: React.ReactNode }) {
  return (
    <div className="grid gap-x-12 lg:grid-cols-[240px_minmax(0,1fr)]">
      <aside>
        <Toc items={toc} />
      </aside>
      <article className="card min-w-0 px-5 py-8 sm:px-10 sm:py-12">
        <nav aria-label="Breadcrumb" className="mb-6 text-sm text-muted">
          <ol className="flex flex-wrap items-center gap-2">
            <li><Link href="/" className="link">Home</Link></li>
            <li aria-hidden>/</li>
            <li aria-current="page">{eyebrow}</li>
          </ol>
        </nav>
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="display mt-3">{title}</h1>
        <div className="lede mt-5 max-w-2xl">{intro}</div>
        <div className="prose-v mt-12">{children}</div>
      </article>
      <BackToTop />
    </div>
  );
}
