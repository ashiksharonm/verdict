import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl py-16 text-center">
      <p className="eyebrow">404</p>
      <h1 className="display mt-3">That page does not exist</h1>
      <p className="lede mt-5">The link may be old or mistyped.</p>
      <div className="mt-8 flex justify-center gap-3">
        <Link href="/" className="btn btn-primary">Back home</Link>
        <Link href="/docs" className="btn btn-ghost">Read the docs</Link>
      </div>
    </div>
  );
}
